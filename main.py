"""
main.py — CLI entry point for testing without Streamlit
Usage: python main.py <path_to_rfp.pdf> [client_name]
"""

import os, sys
from dotenv import load_dotenv

load_dotenv()


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_rfp.pdf> [client_name]")
        print("Example: python main.py uploads/rfp.pdf 'HDFC Bank'")
        sys.exit(1)

    pdf_path    = sys.argv[1]
    client_name = sys.argv[2] if len(sys.argv) > 2 else "Client"

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  TechM RFP Automation System — CLI Mode")
    print(f"  Client: {client_name}")
    print(f"{'='*60}\n")

    print("🔍 Step 1: Extracting RFP text…")
    from ingestor import extract_text_only
    rfp_text = extract_text_only(pdf_path)
    print(f"   ✅ Extracted {len(rfp_text):,} characters\n")

    print("📚 Step 2: Loading knowledge base…")
    from brain import load_knowledge_base
    kb = load_knowledge_base()
    kb_context = kb.query(rfp_text[:600]) if kb.count() > 0 else ""
    print(f"   ✅ KB has {kb.count()} chunks | Context: {len(kb_context)} chars\n")

    print("🤖 Step 3: Running 4-agent AI crew…")
    print("   (This takes 2–4 minutes with Groq Llama3-70b)\n")
    from agents import run_crew
    outputs = run_crew(rfp_text, kb_context)

    print("\n💾 Step 4: Exporting documents…")
    from exporter import export_to_word, export_to_ppt
    word_path = export_to_word(outputs, client_name=client_name)
    ppt_path  = export_to_ppt(outputs,  client_name=client_name)

    print(f"\n{'='*60}")
    print(f"  ✅ Done!")
    print(f"  📄 Word: {word_path}")
    print(f"  📊 PPT:  {ppt_path}")
    print(f"{'='*60}\n")

    print("📝 Proposal Preview (first 1200 chars):\n")
    print(outputs.get("proposal", "")[:1200])
    print("\n…(full proposal in exported files)")


if __name__ == "__main__":
    main()