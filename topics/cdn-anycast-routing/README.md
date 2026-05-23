# CDN Anycast Routing — Accelerating Dynamic APIs

## The Interview Question

> "Your users in Asia are getting slow API responses. Your servers are in Europe. How do you fix it?"

The instinct: "Put a CDN in front of the app." Sounds right. Feels right.

Then the follow-up:

> "If the CDN only caches static images, how does it speed up a dynamic login API call?"

And the whole answer collapses. Because dynamic data has to travel all the way back to the origin server in Europe anyway — caching CSS in Tokyo doesn't help the request that needs to read your `users` table in Frankfurt.

This is the interview question that filters the candidates who memorized "CDNs are for caching" from the ones who actually understand what a modern CDN does.

---

## The Misconception

> "CDNs only help static assets. For dynamic API traffic, they're useless."

Half of the engineering world believes this. It's the most common misunderstanding in system design interviews.

The misconception is built on the *first generation* of CDNs (Akamai in the late 90s) which really were just geographically distributed caches for images, CSS, and JS. If your data was dynamic, the CDN had to forward the request to your origin server — same long-distance trip, same painful latency.

Modern CDNs do something completely different on top of caching. And that "something" is what wins you the interview.

---

## The Three Tricks of Dynamic Acceleration

A modern CDN speeds up dynamic API traffic using three mechanisms that have **nothing to do with caching**:

### Trick 1 — Anycast Routing (Get to the Edge Fast)

**Anycast** is one IP address advertised from hundreds of locations at once. When a user's request leaves their device, BGP routes it to the *topologically closest* edge — not based on distance on a map, but on actual network proximity.

```
User in Tokyo  →  hits 1.1.1.1  →  routes to CDN edge in Tokyo  (~5ms)
User in São Paulo  →  hits 1.1.1.1  →  routes to CDN edge in São Paulo  (~5ms)
User in Berlin  →  hits 1.1.1.1  →  routes to CDN edge in Frankfurt  (~5ms)
```

Same IP, different destination, no DNS magic. The first hop becomes nearly instant *anywhere in the world*.

### Trick 2 — Pre-Warmed TCP & TLS Connections

Once the user is at the edge, the edge has to talk to your origin server. The naive way: open a new TCP connection, do a TLS handshake, send the request. That's **3–5 round trips** before a single byte of payload moves.

Modern CDNs keep a **pool of persistent, already-handshook connections** between every edge and your origin. When your user's request arrives at the Tokyo edge, the edge doesn't dial Europe from scratch — it grabs a connection that's already alive, already authenticated, and just sends the bytes.

```
Cold connection (no CDN):
  TCP SYN/SYN-ACK/ACK   → 1 RTT
  TLS ClientHello/...    → 1–2 RTT
  Request                → 1 RTT
  Total before response: 3–4 RTT

Pre-warmed (CDN edge → origin):
  Request                → 1 RTT (connection already open)
  Total before response: 1 RTT
```

Over a 250ms Asia↔Europe link, that's the difference between a **1 second** API call and a **300ms** API call.

### Trick 3 — Private Backbone (Skip the Public Internet)

Public internet routing is decided by BGP. BGP picks the **shortest path between autonomous systems** — not the lowest-latency one, not the least-congested one. Your packet from Tokyo to Frankfurt might hop through Los Angeles and New York for reasons no one can explain.

CDN providers operate **their own private fiber networks** between every edge and every region. Cloudflare calls it Argo. AWS calls it the Global Accelerator network. Akamai has been doing it for two decades. The CDN forwards your dynamic traffic over its own backbone — measured, optimized, congestion-controlled — instead of the public internet's whatever-BGP-felt-like-today.

---

## The Full Picture

```
Without dynamic acceleration:
  User (Tokyo)  →  public internet  →  origin (Frankfurt)
                 ~250ms, 12 hops, BGP roulette

With dynamic acceleration:
  User (Tokyo)  →  Tokyo edge (Anycast, ~5ms)
                →  persistent connection over CDN backbone
                →  origin (Frankfurt)
                 ~280ms first request, ~30ms thereafter
```

The data still travels — physics doesn't care that you bought Cloudflare. But you skip the handshake tax on every request *and* you skip the public internet's bad routing decisions.

---

## Products That Do This

| Provider | Product name | What it gives you |
|---|---|---|
| **Cloudflare** | Argo Smart Routing | Anycast + private backbone + optimized routing |
| **AWS** | Global Accelerator | Anycast IPs + AWS backbone to your origin |
| **Akamai** | Ion / IPA | The original — Anycast + SureRoute over Akamai's network |
| **Fastly** | Origin Shield + backbone | Persistent connections + their fiber network |
| **Google Cloud** | Premium Tier networking | Routes user traffic over Google's backbone end-to-end |

Most of these are a checkbox in a console. The hard work is already done by the provider — you just opt in.

---

## What Dynamic Acceleration Does Not Fix

It is **not magic**. There are limits.

| Limitation | Why |
|---|---|
| **Database query time** | If your query takes 800ms, the network is the cheapest part of the problem. Profile the query first. |
| **Speed of light** | Tokyo↔Frankfurt is ~250ms round-trip even on perfect fiber. Acceleration shrinks the overhead; it can't shrink the distance. |
| **Sub-100ms requirements in Asia** | If you genuinely need sub-100ms responses for Asian users, the data needs to *be in Asia*. That means read replicas, geo-replication, or a globally distributed database — not a CDN trick. |
| **Bandwidth-bound transfers** | Streaming a 5GB video benefits more from edge caching than from acceleration. |

The honest answer in the interview is: **CDN dynamic acceleration is the cheapest, lowest-effort 30–50% latency win you can buy. After that, you need real geo-distributed infrastructure** — see [How Tinder Finds Matches in Milliseconds](../how-tinder-finds-matches/) for what that looks like, or [How Global Apps Keep You Logged In](../how-global-apps-keep-you-logged-in/) for the session-layer version of the same problem.

---

## The Key Insight

A CDN is two products in one trench coat.

1. The **caching CDN** — what everyone learns first. Stores static assets at the edge.
2. The **acceleration CDN** — what the interview is really testing. Skips public internet, skips handshakes, routes dynamic traffic over a private backbone.

Most engineers only know about (1) and assume (2) doesn't exist. The ones who know about (2) get the offer.

---

## TL;DR

- A modern CDN accelerates dynamic API traffic via **three** mechanisms that have nothing to do with caching: **Anycast routing**, **persistent pre-warmed connections**, and a **private backbone**.
- The user hits the nearest edge in ~5ms. The edge already has an open, authenticated connection to your origin. That connection runs over the CDN's fiber, not the public internet.
- Expect ~30–50% lower API latency over long distances — for the cost of flipping a checkbox.
- It does **not** replace geo-distributed data. If the database is in Frankfurt, the data still has to travel to Frankfurt. Dynamic acceleration optimizes the journey; it doesn't shorten the road.

When the interviewer asks "how does a CDN speed up dynamic traffic," the answer isn't "it caches things." The answer is "Anycast, persistent connections, and a private backbone — caching is a separate feature."

---

## Resources

### Docs
- [What is Anycast? — Cloudflare Learning](https://www.cloudflare.com/learning/cdn/glossary/anycast-network/)
- [Argo Smart Routing — Cloudflare](https://www.cloudflare.com/application-services/products/argo-smart-routing/)
- [AWS Global Accelerator](https://aws.amazon.com/global-accelerator/)
- [Network Service Tiers — Google Cloud](https://cloud.google.com/network-tiers)
