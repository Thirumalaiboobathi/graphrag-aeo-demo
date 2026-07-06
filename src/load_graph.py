import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

CLEAR = "MATCH (n) DETACH DELETE n"

LOAD = """
CREATE (p:Product {name: 'AcmeGraph'})
CREATE (starter:Plan {name: 'Starter', price: 0, currency: 'USD'})
CREATE (team:Plan    {name: 'Team',    price: 99, currency: 'USD'})
CREATE (ent:Plan     {name: 'Enterprise', price: 499, currency: 'USD'})
CREATE (vi:Feature   {name: 'Vector Index'})
CREATE (hs:Feature   {name: 'Hybrid Search'})
CREATE (ml:Feature   {name: 'Multi-Region'})
CREATE (lg:Tool      {name: 'LangGraph'})
CREATE (doc1:Doc {title: 'Hybrid Search Guide',
                  url: 'https://acmegraph.io/docs/hybrid-search.md'})
CREATE (doc2:Doc {title: 'Plans and Pricing',
                  url: 'https://acmegraph.io/docs/pricing.md'})
CREATE (p)-[:HAS_FEATURE]->(vi)
CREATE (p)-[:HAS_FEATURE]->(hs)
CREATE (p)-[:HAS_FEATURE]->(ml)
CREATE (hs)-[:IMPLEMENTED_BY]->(vi)
CREATE (vi)-[:REQUIRES]->(team)
CREATE (ml)-[:REQUIRES]->(ent)
CREATE (hs)-[:DOCUMENTED_IN]->(doc1)
CREATE (p)-[:INTEGRATES_WITH]->(lg)
"""

with driver.session() as s:
    s.run(CLEAR)
    s.run(LOAD)
    count = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    print(f"✅ Loaded {count} nodes into the graph")

driver.close()
