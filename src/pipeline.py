import os
import json
from typing import TypedDict
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langgraph.graph import StateGraph, END
from langchain_aws import ChatBedrock

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

llm = ChatBedrock(
    model_id=os.getenv("BEDROCK_MODEL_ID"),
    region_name=os.getenv("AWS_REGION"),
    model_kwargs={"temperature": 0, "max_tokens": 1000}
)

class GraphRAGState(TypedDict):
    question: str
    entities: list[str]
    facts: list[str]
    hops: int
    answer: str

def extract_entities(state: GraphRAGState) -> dict:
    prompt = (
        "Extract entity names from this question. Look for products, "
        "features, plans, or tools. Respond with ONLY a JSON array of "
        f"strings, no other text.\nQuestion: {state['question']}"
    )
    response = llm.invoke(prompt).content.strip()
    # Strip code fences if the model adds them
    response = response.replace("```json", "").replace("```", "").strip()
    entities = json.loads(response)
    print(f"🔍 Extracted entities: {entities}")
    return {"entities": entities, "hops": 0, "facts": []}

def traverse_graph(state: GraphRAGState) -> dict:
    query = """
    MATCH (e) WHERE e.name IN $names
    MATCH path = (e)-[r*1..2]-(connected)
    RETURN e.name AS entity,
           [rel IN relationships(path) | type(rel)] AS rels,
           connected AS node
    LIMIT 50
    """
    with driver.session() as s:
        rows = s.run(query, names=state["entities"]).data()
    triples = []
    for row in rows:
        node_name = row["node"].get("name") or row["node"].get("title", "?")
        rel_chain = " -> ".join(row["rels"])
        extra = ""
        if "price" in row["node"]:
            extra = f" (price: {row['node']['price']} USD)"
        if "url" in row["node"]:
            extra = f" ({row['node']['url']})"
        triples.append(f"{row['entity']} --{rel_chain}--> {node_name}{extra}")
    triples = list(set(triples))  # dedupe
    print(f"📊 Retrieved {len(triples)} facts")
    return {"facts": state["facts"] + triples,
            "hops": state["hops"] + 1}

def check_sufficiency(state: GraphRAGState) -> str:
    if state["hops"] >= 2:
        return "generate"
    prompt = (
        f"Question: {state['question']}\n"
        f"Facts retrieved:\n" + "\n".join(state["facts"]) +
        "\n\nAre these facts sufficient to answer the question? "
        "Reply with only 'SUFFICIENT' or 'INSUFFICIENT'."
    )
    verdict = llm.invoke(prompt).content.strip().upper()
    print(f"🧠 Sufficiency: {verdict}")
    return "traverse" if "INSUFFICIENT" in verdict else "generate"

def generate_answer(state: GraphRAGState) -> dict:
    prompt = (
        "You are a helpful assistant. Answer the user's question using "
        "ONLY the graph facts below. If facts are insufficient, say so. "
        "Cite specific facts in your answer.\n\n"
        f"Facts:\n" + "\n".join(state["facts"]) +
        f"\n\nQuestion: {state['question']}"
    )
    answer = llm.invoke(prompt).content
    return {"answer": answer}

def build_pipeline():
    g = StateGraph(GraphRAGState)
    g.add_node("extract", extract_entities)
    g.add_node("traverse", traverse_graph)
    g.add_node("generate", generate_answer)
    g.set_entry_point("extract")
    g.add_edge("extract", "traverse")
    g.add_conditional_edges("traverse", check_sufficiency,
                            {"traverse": "traverse",
                             "generate": "generate"})
    g.add_edge("generate", END)
    return g.compile()
