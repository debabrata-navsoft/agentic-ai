"""RAG retrieval: semantic search over documents the user uploaded."""

import json

from pydantic import Field

from app.tools.base import Tool, ToolContext, ToolError, ToolInput


def _kb(ctx: ToolContext):
    if ctx.kb is None:
        raise ToolError("Knowledge base is not configured")
    return ctx.kb


class SearchKnowledgeInput(ToolInput):
    query: str = Field(description="What to look for, phrased as a question or key phrase")
    top_k: int = Field(default=5, ge=1, le=20, description="How many passages to return")


def search_knowledge_base(args: SearchKnowledgeInput, ctx: ToolContext) -> str:
    hits = _kb(ctx).search(ctx.user_id, args.query, args.top_k)
    if not hits:
        return "No relevant passages found. The knowledge base may be empty."
    return json.dumps(hits, indent=2, ensure_ascii=False)


def list_documents(args: ToolInput, ctx: ToolContext) -> str:
    docs = _kb(ctx).list_documents(ctx.user_id)
    if not docs:
        return "No documents uploaded."
    return "\n".join(f"- {d['name']} ({d['chunks']} chunks, uploaded {d['created_at']})" for d in docs)


TOOLS = [
    Tool(
        name="search_knowledge_base",
        label="Search documents",
        description="Semantic search over documents the user uploaded (PDFs, notes, code, etc.). "
        "Returns the most relevant passages with their source file and a similarity score. "
        "Use it whenever the question may be answered by the user's own documents, and cite "
        "the source file names in your answer.",
        input_model=SearchKnowledgeInput,
        handler=search_knowledge_base,
    ),
    Tool(
        name="list_documents",
        label="List documents",
        description="List the documents currently in the knowledge base.",
        input_model=ToolInput,
        handler=list_documents,
    ),
]
