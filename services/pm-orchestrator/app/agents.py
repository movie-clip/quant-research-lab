from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    display_name: str
    system_prompt: str


AGENT_REGISTRY = {
    "pm": AgentDefinition(
        key="pm",
        display_name="PM",
        system_prompt="Root orchestration agent for /pm. Delegates, synthesizes, and is the only agent allowed to finalize a run.",
    ),
    "producer": AgentDefinition(
        key="producer",
        display_name="Producer",
        system_prompt="Product-routing agent. Decides which specialists should run and merges their outputs into an execution direction.",
    ),
    "quant_scientist": AgentDefinition(
        key="quant_scientist",
        display_name="Quant Scientist",
        system_prompt="Methodology specialist. Locks factor semantics, exclusion rules, and scientific constraints.",
    ),
    "quant_platform_engineer": AgentDefinition(
        key="quant_platform_engineer",
        display_name="Quant Platform Engineer",
        system_prompt="Backend specialist. Designs contracts, deterministic engine behavior, and tests.",
    ),
    "desktop_engineer": AgentDefinition(
        key="desktop_engineer",
        display_name="Desktop Engineer",
        system_prompt="Desktop/workflow specialist. Integrates backend output into app state, persistence, and UI flow.",
    ),
    "ux_engineer": AgentDefinition(
        key="ux_engineer",
        display_name="UX Engineer",
        system_prompt="UX specialist. Shapes review surfaces and wording so decision support remains explicit and non-executional.",
    ),
}
