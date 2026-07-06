import sys
from pipeline import build_pipeline

def run(question: str):
    print(f"\n❓ Question: {question}\n" + "─" * 60)
    app = build_pipeline()
    result = app.invoke({
        "question": question,
        "entities": [],
        "facts": [],
        "hops": 0,
        "answer": ""
    })
    print("─" * 60)
    print(f"\n✅ Answer:\n{result['answer']}\n")

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or \
        "Can I use Hybrid Search on the free Starter plan?"
    run(question)
