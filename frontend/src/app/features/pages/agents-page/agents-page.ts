import { Component, computed, inject, signal } from '@angular/core';
import { LucideDynamicIcon } from '@lucide/angular';

import { ChatStore } from '../../../core/services/chat-store';

export interface AgentDef {
  id: string;
  name: string;
  role: string;
  icon: string;
  avatarGradient: string;
  model: string;
  description: string;
  capabilities: string[];
  tools: string[];
  systemFocus: string;
  promptSample: string;
}

@Component({
  selector: 'app-agents-page',
  imports: [LucideDynamicIcon],
  templateUrl: './agents-page.html',
  styleUrl: './agents-page.css',
})
export class AgentsPage {
  protected readonly store = inject(ChatStore);
  protected readonly searchQuery = signal('');

  readonly agents: AgentDef[] = [
    {
      id: 'prime',
      name: 'Synora Prime',
      role: 'Master Orchestrator',
      icon: 'sparkles',
      avatarGradient: 'linear-gradient(135deg, #8b5cf6, #c084fc)',
      model: 'Claude 3.5 Sonnet',
      description: 'The primary general agent capable of autonomous workflow planning, chaining multiple tools, reflection, and end-to-end task execution.',
      capabilities: ['Dynamic Planning', 'Multi-Tool Execution', 'State Verification', 'Long-term Memory'],
      tools: ['Web Search', 'File System', 'Chroma RAG', 'Calculator', 'Save Memory'],
      systemFocus: 'Autonomous orchestration across all available tools.',
      promptSample: 'Plan and execute a complete solution for my task.',
    },
    {
      id: 'research',
      name: 'Deep Research Agent',
      role: 'Live Web & Fact Specialist',
      icon: 'globe',
      avatarGradient: 'linear-gradient(135deg, #3b82f6, #60a5fa)',
      model: 'Claude 3.5 Sonnet',
      description: 'Specialized in real-time internet search, comprehensive synthesis, extracting source citations, and reading live web pages.',
      capabilities: ['Live Web Crawl', 'Citation Verification', 'News Synthesis', 'Literature Analysis'],
      tools: ['web_search', 'fetch_web_page', 'domain_filter'],
      systemFocus: 'Real-time online intelligence with verifiable sources.',
      promptSample: 'Research the latest developments in autonomous AI agents and summarize findings with sources.',
    },
    {
      id: 'coder',
      name: 'Software Engineer Agent',
      role: 'Code & Architecture Specialist',
      icon: 'code',
      avatarGradient: 'linear-gradient(135deg, #10b981, #34d399)',
      model: 'Claude 3.5 Sonnet',
      description: 'Expert in reviewing local repositories, creating new modules, refactoring TypeScript & Python, and sandboxed file operations.',
      capabilities: ['Code Generation', 'Workspace File IO', 'Bug Diagnosis', 'Refactoring'],
      tools: ['read_file', 'write_file', 'list_dir', 'sandbox_exec'],
      systemFocus: 'Precision software engineering, code quality, and local workspace modifications.',
      promptSample: 'Write a Python utility script to process JSON files and save it to my workspace.',
    },
    {
      id: 'rag',
      name: 'Knowledge Base (RAG) Agent',
      role: 'Document Grounding Specialist',
      icon: 'file-search',
      avatarGradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
      model: 'Claude 3.5 Sonnet',
      description: 'Specialized in semantic vector retrieval over your uploaded PDF, text, and markdown files stored in the Chroma vector database.',
      capabilities: ['Chroma Vector Search', 'Passage Extraction', 'Document Synthesis', 'Fact Grounding'],
      tools: ['query_documents', 'list_documents', 'fetch_chunk'],
      systemFocus: 'Accurate question answering strictly grounded in private documents.',
      promptSample: 'Summarize the key takeaways and specific metrics from my uploaded project notes.',
    },
    {
      id: 'quant',
      name: 'Quantitative & Math Agent',
      role: 'Arithmetic & Exact Logic Analyst',
      icon: 'calculator',
      avatarGradient: 'linear-gradient(135deg, #ec4899, #f472b6)',
      model: 'Claude 3.5 Sonnet',
      description: 'Specialized in exact numeric computation, compound interest, algebraic evaluation, statistical breakdown, and time/calendar math.',
      capabilities: ['Exact Arithmetic', 'Financial Math', 'Algorithm Complexity', 'Clock & Date Math'],
      tools: ['calculator', 'clock', 'date_diff'],
      systemFocus: 'Exact mathematical evaluation avoiding LLM hallucinations.',
      promptSample: 'What is the compound interest on ₹2,50,000 at 7.5% for 12 years? Show the full formula breakdown.',
    },
  ];

  protected readonly filteredAgents = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    if (!q) return this.agents;

    return this.agents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        a.role.toLowerCase().includes(q) ||
        a.description.toLowerCase().includes(q) ||
        a.capabilities.some((c) => c.toLowerCase().includes(q)) ||
        a.tools.some((t) => t.toLowerCase().includes(q)),
    );
  });

  protected startChatWith(agent: AgentDef) {
    this.store.newChat();
    this.store.setActiveView('chat');
  }

  protected backToChat() {
    this.store.setActiveView('chat');
  }
}
