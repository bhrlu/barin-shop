"""Caller IP resolution — the one place that decides who "the client" is.

Used by the request middleware in `app.main`, which stores the result in
`audit.client_ip_ctx` for the audit trail (B5.1a) and the contact-form throttle
(B3.11). `X-Forwarded-For` is only believed when the socket peer is a configured
trusted proxy (`settings.trusted_proxies`); otherwise any client could put an
arbitrary address in the header and step around a per-IP limit or forge the
audit trail. The chain is walked right to left — each trusted proxy appends the
address it saw — and the first hop that is not a trusted proxy is the client.
"""

import ipaddress
from collections.abc import Iterable

from app.config import settings

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(spec: str) -> list[Network]:
    """`"10.0.0.1, 172.16.0.0/12"` → networks; blanks ignored, bad entries rejected."""
    return [
        ipaddress.ip_network(part.strip(), strict=False)
        for part in spec.split(",")
        if part.strip()
    ]


TRUSTED_PROXIES: list[Network] = parse_networks(settings.trusted_proxies)


def _is_trusted(address: str, trusted: Iterable[Network]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in net for net in trusted)


def resolve_client_ip(
    peer: str | None,
    forwarded_for: str | None,
    trusted: Iterable[Network] | None = None,
) -> str | None:
    """The client address for this request (None only without a socket peer)."""
    networks = list(TRUSTED_PROXIES if trusted is None else trusted)
    if not forwarded_for or peer is None or not _is_trusted(peer, networks):
        return peer
    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    for hop in reversed(hops):
        if _is_trusted(hop, networks):
            continue
        try:
            return str(ipaddress.ip_address(hop))
        except ValueError:
            # a malformed hop is not an address we can key on — keep the peer
            return peer
    # every hop is inside a trusted network (an internal client behind the
    # proxy): the leftmost entry is the original caller
    return hops[0] if hops else peer
