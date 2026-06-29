"""Opportunity Portfolio — Stage 7.

Groups related opportunities into a hierarchical portfolio.

Hierarchy: domain → opportunity_type → individual opportunities

Example:
  technology/
    open_source/
      Kubernetes
      Transformers
    research/
      GPT-5 Paper
  market/
    infrastructure/
      GPU Cluster

No external graph DB. Pure Python.
"""

from __future__ import annotations

from collections import defaultdict

from app.knowledge.dto import _k_stable_hash
from app.opportunity.dto import (
    Opportunity,
    OpportunityVersionMetadata,
    PortfolioNode,
)


def _node_id(label: str, domain: str, market: str = "") -> str:
    return _k_stable_hash({"label": label.lower(), "domain": domain.lower(), "market": market.lower()})


def build_portfolio(opportunities: list[Opportunity]) -> list[PortfolioNode]:
    """Build a hierarchical portfolio from a flat list of opportunities.

    Returns a list of top-level domain nodes, each containing type sub-nodes.
    """
    if not opportunities:
        return []

    # Group: domain → {type → [opp]}
    domain_type_map: dict[str, dict[str, list[Opportunity]]] = defaultdict(lambda: defaultdict(list))
    for opp in opportunities:
        domain = opp.domain or "general"
        opp_type = opp.opportunity_type.value
        domain_type_map[domain][opp_type].append(opp)

    top_nodes: list[PortfolioNode] = []

    for domain, type_map in sorted(domain_type_map.items()):
        domain_opps = [o for opps in type_map.values() for o in opps]
        domain_score = (
            sum(o.score.composite_score for o in domain_opps) / len(domain_opps)
            if domain_opps else 0.0
        )

        children: list[PortfolioNode] = []
        for opp_type, opps in sorted(type_map.items()):
            type_score = sum(o.score.composite_score for o in opps) / len(opps)
            children.append(PortfolioNode(
                node_id=_node_id(opp_type, domain),
                label=opp_type,
                domain=domain,
                market="",
                opportunity_count=len(opps),
                opportunity_ids=sorted(o.opportunity_id for o in opps),
                children=[],
                composite_score=round(type_score, 4),
            ))

        top_nodes.append(PortfolioNode(
            node_id=_node_id(domain, domain),
            label=domain,
            domain=domain,
            market="",
            opportunity_count=len(domain_opps),
            opportunity_ids=sorted(o.opportunity_id for o in domain_opps),
            children=children,
            composite_score=round(domain_score, 4),
        ))

    return top_nodes
