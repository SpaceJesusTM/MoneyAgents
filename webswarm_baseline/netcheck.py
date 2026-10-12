"""Why is web search failing? A read-only check that separates the possible causes.

    .venv/bin/python -m webswarm_baseline.netcheck            # about 30 s
    .venv/bin/python -m webswarm_baseline.netcheck --json

It looks at four things, in the order a request meets them:

  1. the local network   is there an IPv6 route; how long do name lookups take with and without AAAA
  2. the providers       does each search host answer a plain HTTPS request over IPv4, and with what
  3. the search library  does `ddgs` get results as-is, and through the IPv4-only tunnel
  4. our own code        does `DDGSProvider` (what the agents use) return results

and prints which of these is responsible: local network, provider outage, rate limiting, or an
internal error. It changes no system setting and sends a handful of ordinary search requests.
"""
from __future__ import annotations

import json
import socket
import sys
import time

import requests

from .web import DDGSProvider, Ipv4Tunnel, SearchFailure, classify_ddgs_error, ipv6_route

HOSTS = ("html.duckduckgo.com", "search.brave.com", "www.mojeek.com", "search.yahoo.com")
ENDPOINTS = {"duckduckgo": "https://html.duckduckgo.com/html/?q=annual+report",
             "brave": "https://search.brave.com/search?q=annual+report&source=web",
             "mojeek": "https://www.mojeek.com/search?q=annual+report",
             "yahoo": "https://search.yahoo.com/search?p=annual+report"}
BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"


def lookup(host: str, family: int) -> float | None:
    t0 = time.perf_counter()
    try:
        socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM)
    except OSError:
        return None
    return round(time.perf_counter() - t0, 2)


def ask_ddgs(backend: str, proxy: str | None, timeout: int = 10) -> dict:
    from ddgs import DDGS
    t0 = time.perf_counter()
    try:
        rows = DDGS(timeout=timeout, proxy=proxy).text("annual report 10-K filing", max_results=3, backend=backend)
        return {"results": len(rows), "secs": round(time.perf_counter() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        secs = time.perf_counter() - t0
        outcome = classify_ddgs_error(e, secs, timeout)
        kind = outcome.kind if isinstance(outcome, SearchFailure) else "empty"
        return {"results": 0, "secs": round(secs, 1), "kind": kind, "error": str(e)[:120]}


def check() -> dict:
    out: dict = {"ipv6_route": ipv6_route(), "lookups": {}, "providers": {}, "ddgs": {}}
    for host in HOSTS:
        out["lookups"][host] = {"a_only_s": lookup(host, socket.AF_INET), "a_and_aaaa_s": lookup(host, socket.AF_UNSPEC)}
    import urllib3.util.connection as conn
    conn.allowed_gai_family = lambda: socket.AF_INET          # this process only
    for name, url in ENDPOINTS.items():
        t0 = time.perf_counter()
        try:
            r = requests.get(url, headers={"User-Agent": BROWSER}, timeout=(5, 10))
            body = r.text.lower()
            out["providers"][name] = {"http": r.status_code, "secs": round(time.perf_counter() - t0, 2),
                                      "challenge_page": r.status_code in (202, 403, 429) or "anomaly" in body or "captcha" in body}
        except requests.RequestException as e:
            out["providers"][name] = {"http": 0, "secs": round(time.perf_counter() - t0, 2), "error": type(e).__name__}
    tunnel = Ipv4Tunnel()
    try:
        out["ddgs"]["auto, as installed"] = ask_ddgs("auto", None)
        for backend in ("duckduckgo", "brave", "auto"):
            out["ddgs"][f"{backend}, via IPv4 tunnel"] = ask_ddgs(backend, tunnel.url)
    finally:
        tunnel.close()
    t0 = time.perf_counter()
    try:
        out["our_provider"] = {"results": len(DDGSProvider().search("annual report 10-K filing", 3)),
                               "secs": round(time.perf_counter() - t0, 1)}
    except SearchFailure as f:
        out["our_provider"] = {"results": 0, "kind": f.kind, "secs": round(time.perf_counter() - t0, 1), "error": f.detail[:120]}
    out["verdict"] = verdict(out)
    return out


def verdict(c: dict) -> list[str]:
    v = []
    slow = [h for h, t in c["lookups"].items() if t["a_only_s"] is not None and (t["a_and_aaaa_s"] or 99) - t["a_only_s"] > 1.0]
    dead = [h for h, t in c["lookups"].items() if t["a_only_s"] is None]
    if dead:
        v.append(f"LOCAL NETWORK: names do not resolve at all ({', '.join(dead)}). No connection, or DNS is down.")
    if slow:
        v.append(f"LOCAL NETWORK: lookups that ask for IPv6 addresses take seconds longer than IPv4-only ones "
                 f"({len(slow)} of {len(c['lookups'])} hosts){'' if c['ipv6_route'] else ', and this machine has no IPv6 route'}. "
                 "The resolver is dropping AAAA queries. Any client that waits for them loses that time on every connection.")
    down = [n for n, p in c["providers"].items() if p["http"] == 0]
    limited = [n for n, p in c["providers"].items() if p.get("challenge_page")]
    if down and not dead:
        v.append(f"PROVIDER OUTAGE or block: no HTTPS answer over IPv4 from {', '.join(down)}.")
    if limited:
        v.append(f"RATE LIMITING / bot challenge: {', '.join(limited)} answered a plain request with a challenge or "
                 "refusal. The search library reports this as 'no results'.")
    raw, tun = c["ddgs"]["auto, as installed"], c["ddgs"]["auto, via IPv4 tunnel"]
    if not raw["results"] and tun["results"]:
        v.append("SEARCH LIBRARY: ddgs fails as installed and works through the IPv4-only tunnel, so the local "
                 "name-lookup problem is what breaks it.")
    if not raw["results"] and not tun["results"] and not dead:
        v.append(f"SEARCH LIBRARY: ddgs gets nothing either way ({tun.get('kind', '?')}). Providers are limiting or down.")
    if c["our_provider"]["results"]:
        v.append("OUR CODE: DDGSProvider returns results. Agents can search.")
    else:
        v.append(f"OUR CODE: DDGSProvider gets no answer ({c['our_provider'].get('kind')}). Agents cannot search; "
                 "runs will report retrieval failures rather than empty results, and nothing is recorded.")
    return v or ["No problem found."]


def main() -> None:
    c = check()
    if "--json" in sys.argv:
        print(json.dumps(c, indent=2))
        return
    print(f"IPv6 route: {'yes' if c['ipv6_route'] else 'NO'}")
    print("Name lookups (seconds; IPv4 only / IPv4 and IPv6):")
    for host, t in c["lookups"].items():
        print(f"  {host:24} {t['a_only_s']} / {t['a_and_aaaa_s']}")
    print("Plain HTTPS request to each search host, over IPv4:")
    for name, p in c["providers"].items():
        print(f"  {name:11} HTTP {p['http']} in {p['secs']} s" + ("  <- challenge / refusal" if p.get("challenge_page") else "")
              + (f"  ({p['error']})" if p.get("error") else ""))
    print("ddgs:")
    for name, r in c["ddgs"].items():
        print(f"  {name:28} {r['results']} results in {r['secs']} s" + (f"  [{r['kind']}]" if r.get("kind") else ""))
    o = c["our_provider"]
    print(f"DDGSProvider (used by the agents): {o['results']} results in {o['secs']} s" + (f"  [{o['kind']}]" if o.get("kind") else ""))
    print("\nVerdict:")
    for line in c["verdict"]:
        print("  - " + line)


if __name__ == "__main__":
    main()
