# tests/run_parser_test.py
from src import parser

def main():
    path = "samples/sample_resume.pdf"  # change path if you placed PDF elsewhere
    print("Using path:", path)
    try:
        r = parser.parse_and_extract(path)
    except Exception as e:
        print("Parser error:", e)
        return

    print("---- TEXT PREVIEW (first 500 chars) ----")
    txt = r.get("text", "")
    print(txt[:500].replace("\n", "\\n"))
    print("\n---- SECTIONS ----")
    sections = r.get("sections", {})
    if not sections:
        print("No sections detected")
    else:
        for k, v in sections.items():
            print("SECTION:", k)
            print(v[:200].replace("\n", "\\n"))
            print("---")
    print("\n---- SKILLS ----")
    print(r.get("skills", []))

if __name__ == '__main__':
    main()
