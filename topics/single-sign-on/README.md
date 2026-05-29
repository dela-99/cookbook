# Single Sign-On (SSO)

## The Interview Question

> "Explain Single Sign-On."

Most candidates start with *"so you log in once and you're logged into everything"* — and the interviewer nods, waiting.

Then the kill-shot:

> "Where does the trust actually live? When App B logs you in, what is it *trusting*?"

If you can't answer that, you don't understand SSO — you understand a marketing line. SSO isn't a session trick. It's a **federated trust system** built on cryptographic signatures. One central authority vouches for who you are. Every app in your ecosystem trusts that authority's signature, and only that authority's signature.

The moment you understand SSO as "federated trust, not shared sessions," the rest of the architecture falls out naturally.

---

## The Resort Wristband Analogy

Imagine you're staying at a nice resort.

Instead of handing you separate keys for the gym, the pool, and your room, the front desk gives you **one wristband** at check-in. The wristband is marked with the resort's stamp — every facility recognizes that stamp and waves you in.

The wristband is **not your identity**. It's a *signed token* that says "the resort verified this person at the front desk at 9:14 AM, valid until checkout." The pool attendant doesn't call the front desk to confirm — they look at the stamp and trust it.

SSO is that wristband for software:

- The **front desk** is your **Identity Provider (IdP)** — Okta, Auth0, Azure AD, Google Workspace
- The **wristband** is a signed token — usually a **JWT** or a **SAML assertion**
- The **gym, pool, and room** are **Service Providers (SPs)** — Slack, Salesforce, GitHub, your internal apps
- The **stamp** is a cryptographic signature that every SP can verify, but only the IdP can produce

---

## The Flow — What Actually Happens When You Click "Login"

The typical SP-initiated SSO flow:

```
1.  You click "Login with Okta" on slack.com
2.  Slack (the SP)       →  302 Redirect       →  okta.com (the IdP)
                            "I need an auth assertion for this user"
3.  Okta authenticates you (password, MFA, etc.)
4.  Okta                 →  signs a token       →  redirects back to Slack
                            (JWT or SAML assertion)
5.  Slack verifies the signature using Okta's public key
6.  Slack creates a local session and logs you in
```

The crucial step is **5**. Slack doesn't call Okta to ask "is this user real?" It cryptographically verifies that the token came from Okta — using a public key it already has — and trusts what the token says about you. **The trust lives in the signature.**

---

## How the Signature Verification Actually Works

This is the part most engineers wave their hands at.

The IdP holds a **private key**. It uses that private key to sign every token it issues. The signature is included inside the token itself.

Every SP knows the IdP's **public key**, usually fetched from a well-known URL:

```
https://my-idp.okta.com/.well-known/jwks.json
```

`JWKS` is "JSON Web Key Set" — it's the IdP saying *"here are my public keys; use them to verify any token claiming to be from me."*

When Slack receives the token, it:

1. Parses the token header to see which key was used
2. Looks up that key in the JWKS
3. Recomputes the signature locally using the public key
4. If the signatures match → the token is authentic, untampered, and from the IdP

This is why SSO scales: **verification is local and stateless**. The IdP doesn't need to be online for Slack to verify a token. The crypto is the trust.

---

## SAML vs OIDC — Two Token Formats, One Idea

There are two dominant SSO protocols. Same conceptual flow; different on the wire.

| Aspect | **SAML 2.0** | **OIDC (OpenID Connect)** |
|---|---|---|
| **Token format** | XML assertion | JSON Web Token (JWT) |
| **Underlying protocol** | SOAP-style, browser POSTs | Built on OAuth 2.0 |
| **Best for** | Legacy enterprise (Salesforce, Workday, anything pre-2014) | Modern apps, mobile, SPAs |
| **Token transport** | POST to ACS URL | Authorization code → token exchange |
| **Discovery** | Metadata XML files | `.well-known/openid-configuration` |
| **Signing** | XML-DSig | JWS (JSON Web Signatures) |

If you're building B2B SaaS today, you offer **both**. Your enterprise customers' security teams will require SAML for the IT-mandated apps and OIDC for everything new. Treat them as two adapters around the same `verify(token) → user_identity` contract.

---

## The Single Point of Failure

The wristband analogy has a dark version: **if someone steals your wristband, they get access to everything you do**. SSO has the same problem at internet scale.

A stolen SSO token isn't a Slack token or a Salesforce token — it's an *every-app-you-own* token. The blast radius of a single credential leak is the full ecosystem.

Worse: **if your IdP goes down, every app in your ecosystem effectively goes down too.** Nobody can log in anywhere. The Okta outage of March 2022 took out Slack, Zoom, GitHub Enterprise, Salesforce, and a long tail of customer applications — for hours — because the entire industry had centralized identity onto one provider.

You're not buying convenience for free. You're trading "one stolen password = one compromised app" for "one stolen wristband = everything." The trade is worth it, but only if you defend the wristband properly.

---

## How You Defend the IdP

| Defense | What it does |
|---|---|
| **Multi-Factor Authentication (MFA)** | Required at the IdP, not at every SP. The wristband is hard to forge because the front desk asks for ID *and* a fingerprint. |
| **Short-lived access tokens** | 5–60 minutes. A stolen token is dangerous for an hour, not forever. |
| **Refresh token rotation** | Each refresh issues a new refresh token *and invalidates the old one*. A stolen refresh token gets you exactly one use before the legitimate user's next refresh kicks it out. See [JWT Refresh (Token Rotation)](../../live-coding/jwt-refresh/) for the working implementation. |
| **Step-up authentication** | High-risk actions (admin panel, payment changes) require fresh MFA even if the SSO session is still valid. |
| **Conditional access** | The IdP blocks logins from unknown locations, unmanaged devices, or impossible-travel patterns. |
| **Audit logging at the IdP** | Every authentication event in one place. When something goes wrong, the IdP is the canonical source of "who logged in where, when." |
| **Token binding** | Cryptographically bind the token to the device it was issued on (DPoP, mTLS). A token stolen off device B can't be replayed from device A. |

The pattern is: **invest heavily in IdP security, and keep tokens short-lived everywhere downstream.**

---

## Production Considerations

| Decision | What to think about |
|---|---|
| **Pick OIDC for new apps** | SAML is fine for legacy interop, but new apps should default to OIDC. JSON parsers everywhere, way fewer XML-signature pitfalls. |
| **Don't roll your own** | Use Auth0, Okta, Cognito, Azure AD, Keycloak. SSO has a long history of subtle, catastrophic bugs (SAML XML signature wrapping, JWT `alg: none`). Buy or use the open-source giants. |
| **Plan for IdP outage** | At minimum, decide what your app does when the IdP is unreachable. "Hard fail" is honest. "Cache last-known-good tokens for N minutes" is risky but sometimes acceptable. "Local username/password fallback for admins only" is the most common compromise. |
| **Logout is hard** | An SSO logout from one app does *not* automatically log you out everywhere. If you need that, you implement Single Logout (SLO) — and it's notoriously flaky. Most teams just rely on token expiry. |
| **Just-in-time provisioning** | When a new user logs in for the first time, the SP should create the account from the IdP token's claims (email, name, groups). Don't make admins pre-create every user. |
| **Group claims for authorization** | The IdP knows who's in `engineering` and who's in `finance`. Embed those groups in the token so every SP can do role-based access control without a second lookup. |

---

## The Key Insight

SSO isn't a session pattern. It's a **trust pattern**.

The IdP says: "I have verified this user." Every SP says: "I trust the IdP, and I can prove this token came from them." That's it. The whole industry of identity providers exists to be the *one place* that does the hard work — MFA, conditional access, audit, compliance — so every other app gets to be lazy about authentication and still be secure.

When you understand SSO as federated trust, the architectural decisions become obvious:
- Why verification is local and stateless (crypto, not API calls)
- Why the IdP is the most defended box in your infrastructure (everything depends on it)
- Why short-lived tokens matter so much (a stolen wristband should expire fast)
- Why MFA belongs at the IdP, not at every app (defense in depth, but in one place)

---

## TL;DR

- **SSO is federated trust**, not shared sessions. One Identity Provider (IdP) issues signed tokens; every Service Provider (SP) verifies them locally using the IdP's public key.
- The flow: **SP redirects → IdP authenticates → IdP signs a token (JWT or SAML) → SP verifies the signature → user is logged in**.
- **SAML** for legacy enterprise; **OIDC (on top of OAuth 2.0)** for everything modern. If you're B2B SaaS, support both.
- The trade: convenience and central security investment, in exchange for a single point of failure. A stolen IdP token is an *everything* token. An IdP outage takes down every app.
- **Defenses live at the IdP:** MFA, short token lifetimes, refresh-token rotation, conditional access, step-up auth, audit logging.
- **Don't build it yourself.** Use Okta, Auth0, Cognito, Azure AD, or Keycloak. The protocol has too many subtle traps.

When the interview asks "explain SSO," don't say "you log in once." Say "one provider signs a token, every app verifies the signature, and the trust lives in the cryptography."

---

## Related

- [How Global Apps Keep You Logged In](../how-global-apps-keep-you-logged-in/) — the session-layer story underneath every SSO login
- [JWT Refresh (Token Rotation)](../../live-coding/jwt-refresh/) — the working implementation of short-lived access tokens + revocable refresh tokens
- [Pre-Deployment Checklist](../pre-deployment-checklist/) — auth fits into the broader production-readiness picture

---

## Resources

### Specs & Docs
- [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0.html)
- [SAML 2.0 Technical Overview](https://www.oasis-open.org/committees/download.php/27819/sstc-saml-tech-overview-2.0-cd-02.pdf)
- [OAuth 2.0 — RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [JWT — RFC 7519](https://datatracker.ietf.org/doc/html/rfc7519)
- [JWKS — RFC 7517](https://datatracker.ietf.org/doc/html/rfc7517)

### Providers
- [Auth0 — Identity Platform Docs](https://auth0.com/docs)
- [Okta — Developer Docs](https://developer.okta.com)
- [Keycloak — Open-source IAM](https://www.keycloak.org/documentation)
