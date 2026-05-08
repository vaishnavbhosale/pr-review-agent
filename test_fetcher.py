from app.agents.fetcher import FetcherAgent

agent = FetcherAgent()

# Replace this with a real public GitHub repo and a real PR number
context = agent.run("microsoft/vscode", 315184)

print("PR Title:", context.title)
print("Author:", context.author)
print("Files changed:", len(context.files))
print("Base branch:", context.base_branch)
print("Head branch:", context.head_branch)

for f in context.files:
    print(f"\nFile: {f.filename}")
    print(f"Status: {f.status}")
    print(f"Additions: {f.additions}, Deletions: {f.deletions}")
    print("\n--- PATCH PREVIEW OF FIRST FILE ---")
    print(context.files[0].patch[:500])