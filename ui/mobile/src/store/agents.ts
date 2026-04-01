import { create } from 'zustand';
import type { Agent } from '../types';

interface AgentsState {
  activeAgents: Agent[];
  currentAgentId: string | null;
  streamingOutput: string;
  isWorking: boolean;
  setActiveAgents: (agents: Agent[]) => void;
  setCurrentAgent: (id: string | null) => void;
  appendAgentDelta: (agentId: string, delta: string) => void;
  clearAgentOutput: () => void;
  setIsWorking: (working: boolean) => void;
}

export const useAgentsStore = create<AgentsState>((set, get) => ({
  activeAgents: [],
  currentAgentId: null,
  streamingOutput: '',
  isWorking: false,

  setActiveAgents: (agents) => set({ activeAgents: agents }),

  setCurrentAgent: (id) => set({ currentAgentId: id, streamingOutput: '' }),

  appendAgentDelta: (agentId, delta) => {
    if (get().currentAgentId === agentId) {
      set((state) => ({ streamingOutput: state.streamingOutput + delta }));
    }
  },

  clearAgentOutput: () => set({ streamingOutput: '' }),

  setIsWorking: (working) => set({ isWorking: working }),
}));
