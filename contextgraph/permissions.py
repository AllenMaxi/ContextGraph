from __future__ import annotations

from .models import Claim, Visibility


def can_access_claim(
    requester_agent_id: str,
    requester_org_id: str,
    claim: Claim,
) -> bool:
    """Evaluate whether a requester can access a claim.

    Permission model (agent chooses at store time):
      - private:   only the source agent
      - org:       all agents in the same org
      - shared:    specific agent_ids or org_ids in access_list
      - published: any authenticated agent
    """
    # Source agent always has access to their own claims
    if claim.source_agent_id == requester_agent_id:
        return True

    if claim.visibility == Visibility.PRIVATE:
        return False

    if claim.visibility == Visibility.ORG:
        return requester_org_id == claim.source_org_id

    if claim.visibility == Visibility.SHARED:
        return requester_agent_id in claim.access_list or requester_org_id in claim.access_list

    return claim.visibility == Visibility.PUBLISHED
