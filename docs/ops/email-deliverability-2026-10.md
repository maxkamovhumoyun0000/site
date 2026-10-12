# Diamond Education transactional email deliverability

The server signs `no-reply@diamond-education.uz` verification emails with the
private 2048-bit DKIM selector `s202610`. The private key is server-only and
must never be copied into Git, a DNS panel, an app, or chat.

## DNS changes still required in the provider panel

The public MX check on 2026-10-12 found these delivery blockers:

- reverse DNS for `31.220.87.193` is still `vmi3272465.contaboserver.net`;
- DMARC is monitoring-only (`p=none`);
- the newly configured DKIM selector has not yet been published.

### 1. Publish the new DKIM record

In the authoritative DNS panel, create this TXT record. Paste the quoted
pieces as one TXT value; DNS providers may split them automatically.

```text
Host/name: s202610._domainkey
Type: TXT
TTL: 3600
Value: v=DKIM1; h=sha256; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAyi+6qpZ0p6Gd/OH1ioRHCss2j9K4K4LCu6XjtpXsRMYj+vP9E6TJUviUrx9leZJ5KDoWrc1EAu+sS80lFIGAm7L2uRcl/w3rQGbyKM66qVgg/Ys5+R8dtb9sEL88vm+rKfYJa04KWWyqZJn/K1ZUJ0vf1/n/GukdLiZZe1nrZV2T0mU0gPz/9U7LC9LebgI80/cuKeQwHN2Yd0UTpcOZlO7ifwQQzEXtH0YAkUmMKx3lQsBBUgmyoRFlPVeg1pcA633bM6Gg9lxg+OKxtY7APi+m7fQwPjmFGHXZ43CB35fjDLMp9Ws3EgYtj1j3TfwNV7ebxqyMocnI3JjDroM+dQIDAQAB
```

Do **not** remove the existing `default._domainkey` record until mail headers
from the new selector show `dkim=pass`.

### 2. Set the Contabo reverse DNS / PTR

In Contabo Customer Control Panel, set the reverse DNS for `31.220.87.193`
to exactly:

```text
mail.diamond-education.uz
```

Its forward A record already must point to the same IP. This forward-confirmed
PTR is required by major recipient providers.

### 3. Tighten SPF and DMARC safely

Keep every legitimate sending service in SPF. If this server is the only
sender, replace the current soft-fail record with:

```text
v=spf1 ip4:31.220.87.193 -all
```

After DKIM and SPF pass in message headers for 7 days, replace the DMARC TXT
record with this staged policy (use a monitored mailbox for aggregate reports):

```text
v=DMARC1; p=quarantine; pct=25; adkim=s; aspf=s; rua=mailto:dmarc@diamond-education.uz; ruf=mailto:dmarc@diamond-education.uz; fo=1
```

After another 7–14 clean days, use `pct=100`; only then consider `p=reject`.
Do not enable BIMI until DMARC enforcement is at 100% and a compatible logo
certificate is available.

## Verify after DNS propagates

```bash
ssh -i /home/xumoyun-maxkamov/.ssh/myserver.key root@31.220.87.193 \
  'opendkim-testkey -d diamond-education.uz -s s202610 -k /etc/opendkim/keys/diamond-education.uz/s202610.private -vvv'
```

Send one opt-in test verification email to Gmail and inspect **Show original**.
It must show `spf=pass`, `dkim=pass` for `d=diamond-education.uz`, and
`dmarc=pass`. Register the domain in Gmail Postmaster Tools and keep reported
spam rate under 0.3%.
