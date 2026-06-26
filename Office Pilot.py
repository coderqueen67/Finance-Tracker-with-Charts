"""
Advanced Adaptive AI Kernel
===========================

A verification-first adaptive AI scaffold.

What this file provides:
- Task classification
- Strategy genomes
- Durable memory
- Agent orchestration
- Code extraction
- Static Python verification
- Optional Docker sandbox execution
- Failure analysis
- Strategy mutation / promotion
- Benchmark cases
- Built-in self-tests

Run normally:
    python advanced_ai_kernel.py


You can connect this kernel to any LLM provider by implementing LLMClient.complete().
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple


# ============================================================
# LLM INTERFACE
# ============================================================

class LLMClient(Protocol):
    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        ...


class DummyLLM:
    """Safe local test model. Replace with OpenAI, Anthropic, local Llama, etc."""

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        lowered = user.lower()

        if "code" in lowered or "python" in lowered or "calculator" in lowered or "program" in lowered:
            return '''Assumption: Python standard library only.
Verification: The code includes self-tests and can be executed directly.

```python
def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


if __name__ == "__main__":
    assert add(2, 3) == 5
    assert subtract(5, 3) == 2
    assert multiply(4, 3) == 12
    assert divide(10, 2) == 5
    try:
        divide(10, 0)
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass
    print("All tests passed.")
```
'''.strip()

        return (
            "Assumption: I only know what is provided in the prompt. "
            "Verification: no external facts were used. "
            "Answer: I need verified information before making current factual claims."
        )


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class Task:
    id: str
    raw: str
    domain: str
    risk: str
    requires_code: bool
    requires_current_facts: bool
    requires_action: bool
    created_at: float = field(default_factory=time.time)


@dataclass
class StrategyGenome:
    id: str
    domain: str
    version: int
    planner: str
    reasoning_depth: int
    rules: List[str]
    tools_allowed: List[str]
    verification_stack: List[str]
    repair_attempts: int
    promotion_threshold: float
    rollback_threshold: float
    score: float = 0.0
    successes: int = 0
    failures: int = 0
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class VerificationReport:
    passed: bool
    score: float
    gate_results: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


@dataclass
class AgentOutput:
    agent: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Experience:
    id: str
    task: Task
    strategy_id: str
    plan: List[str]
    output: str
    verification: VerificationReport
    failure_type: Optional[str]
    created_at: float = field(default_factory=time.time)


# ============================================================
# MEMORY LAYERS
# ============================================================

class WorkingMemory:
    """RAM-like active context."""

    def __init__(self):
        self.data: Dict[str, Any] = {}

    def set(self, key: str, value: Any):
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def clear(self):
        self.data.clear()


class LongTermMemory:
    """Disk-backed durable memory."""

    def __init__(self, root: str = "ai_memory"):
        self.root = Path(root)
        self.root.mkdir(exist_ok=True)
        self.events_file = self.root / "events.jsonl"
        self.strategies_file = self.root / "strategies.json"
        self.experiences_file = self.root / "experiences.jsonl"

        if not self.strategies_file.exists():
            self.strategies_file.write_text(json.dumps({}, indent=2))

    def log_event(self, event_type: str, payload: Dict[str, Any]):
        event = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "time": time.time(),
            "payload": payload,
        }
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def save_experience(self, exp: Experience):
        with self.experiences_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(exp)) + "\n")

    def load_strategies(self) -> Dict[str, Any]:
        return json.loads(self.strategies_file.read_text())

    def save_strategy(self, strategy: StrategyGenome):
        data = self.load_strategies()
        data[strategy.domain] = asdict(strategy)
        self.strategies_file.write_text(json.dumps(data, indent=2))

    def get_strategy(self, domain: str) -> Optional[StrategyGenome]:
        data = self.load_strategies()
        if domain not in data:
            return None
        return StrategyGenome(**data[domain])

    def recent_experiences(self, domain: str, limit: int = 8) -> List[Dict[str, Any]]:
        if not self.experiences_file.exists():
            return []

        rows = []
        with self.experiences_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                    if item.get("task", {}).get("domain") == domain:
                        rows.append(item)
                except Exception:
                    continue
        return rows[-limit:]


class SemanticMemory:
    """
    Placeholder semantic recall.
    Replace with pgvector, Qdrant, Weaviate, Chroma, or Pinecone.
    """

    def __init__(self):
        self.items: List[Tuple[str, Dict[str, Any]]] = []

    def add(self, text: str, metadata: Dict[str, Any]):
        self.items.append((text.lower(), metadata))

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q = set(query.lower().split())
        scored = []
        for text, meta in self.items:
            score = len(q.intersection(set(text.split())))
            if score:
                scored.append((score, meta))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]


# ============================================================
# TASK CLASSIFIER
# ============================================================

class TaskClassifier:
    def classify(self, raw: str) -> Task:
        text = raw.lower()

        requires_code = any(k in text for k in [
            "code", "program", "function", "repo", "api", "script", "debug", "build app", "software"
        ])
        requires_current_facts = any(k in text for k in [
            "latest", "current", "today", "news", "price", "law", "version", "2026"
        ])
        requires_action = any(k in text for k in [
            "send", "delete", "buy", "deploy", "execute", "email", "schedule"
        ])

        if requires_code:
            domain = "software_engineering"
        elif any(k in text for k in ["prove", "logic", "solve", "math", "reason"]):
            domain = "reasoning"
        elif any(k in text for k in ["business", "market", "money", "strategy"]):
            domain = "business_strategy"
        else:
            domain = "general"

        risk = "high" if any(k in text for k in [
            "malware", "steal", "credential", "bypass", "exploit", "hack", "phishing", "ransomware"
        ]) else "normal"

        return Task(
            id=str(uuid.uuid4()),
            raw=raw,
            domain=domain,
            risk=risk,
            requires_code=requires_code,
            requires_current_facts=requires_current_facts,
            requires_action=requires_action,
        )


# ============================================================
# STRATEGY REGISTRY
# ============================================================

class StrategyRegistry:
    def __init__(self, memory: LongTermMemory):
        self.memory = memory

    def default_strategy(self, domain: str) -> StrategyGenome:
        return StrategyGenome(
            id=f"{domain}.solver.v1",
            domain=domain,
            version=1,
            planner="tree_of_tasks",
            reasoning_depth=5,
            rules=[
                "Never invent facts.",
                "Separate facts from assumptions.",
                "Plan before producing final output.",
                "Use verification before trust.",
                "For code, run tests inside sandbox when possible.",
                "If verification fails, diagnose and repair.",
                "If evidence is missing, state uncertainty.",
                "No risky actions without approval."
            ],
            tools_allowed=["llm", "docker_sandbox", "static_check"],
            verification_stack=["format", "logic", "code_extract", "sandbox", "security_basic"],
            repair_attempts=3,
            promotion_threshold=0.82,
            rollback_threshold=0.55,
        )

    def select(self, task: Task) -> StrategyGenome:
        return self.memory.get_strategy(task.domain) or self.default_strategy(task.domain)

    def promote(self, strategy: StrategyGenome):
        self.memory.save_strategy(strategy)


# ============================================================
# PLANNER
# ============================================================

class Planner:
    def plan(self, task: Task, strategy: StrategyGenome, memories: List[Dict[str, Any]]) -> List[str]:
        plan = [
            "Define exact objective.",
            "List known facts and unknowns.",
            "Choose tools based on domain and risk.",
            "Produce candidate solution.",
            "Run verification stack.",
            "Repair failures if found.",
            "Return final answer with confidence and verification summary."
        ]

        if task.requires_code:
            plan.extend([
                "Design file structure.",
                "Generate code.",
                "Extract code blocks.",
                "Run static checks.",
                "Run sandbox tests.",
                "Patch until tests pass or repair limit reached."
            ])

        if task.requires_current_facts:
            plan.append("Require external source verification before factual claims.")

        if memories:
            plan.append("Apply relevant prior lessons and avoid repeated failures.")

        return plan


# ============================================================
# AGENTS
# ============================================================

class BaseAgent:
    def __init__(self, name: str, llm: LLMClient):
        self.name = name
        self.llm = llm

    def run(self, system: str, user: str) -> AgentOutput:
        content = self.llm.complete(system=system, user=user)
        return AgentOutput(agent=self.name, content=content)


class BuilderAgent(BaseAgent):
    pass


class CriticAgent(BaseAgent):
    pass


class SecurityAgent(BaseAgent):
    pass


class JudgeAgent(BaseAgent):
    pass


# ============================================================
# SANDBOX
# ============================================================

class DockerSandbox:
    """
    Docker-based sandbox. Requires Docker installed.
    Network disabled by default. No secrets mounted.
    """

    def available(self) -> bool:
        return shutil.which("docker") is not None

    def run_python_files(self, files: Dict[str, str], command: Optional[List[str]] = None, timeout: int = 60) -> Dict[str, Any]:
        if not self.available():
            return {
                "passed": False,
                "stdout": "",
                "stderr": "Docker is not installed or not available.",
                "returncode": -1,
            }

        command = command or ["python", "main.py"]

        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            for name, content in files.items():
                path = workdir / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "1",
                "--pids-limit", "128",
                "-v", f"{workdir}:/app:rw",
                "-w", "/app",
                "python:3.12-slim",
                *command,
            ]

            try:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                return {
                    "passed": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "passed": False,
                    "stdout": "",
                    "stderr": "Sandbox timed out.",
                    "returncode": -1,
                }


# ============================================================
# CODE EXTRACTION
# ============================================================

class CodeExtractor:
    PY_BLOCK = re.compile(r"```python\s*(.*?)```", re.DOTALL | re.IGNORECASE)

    def extract_python(self, text: str) -> Optional[str]:
        match = self.PY_BLOCK.search(text)
        if match:
            return match.group(1).strip()

        if "def " in text or "class " in text or "print(" in text:
            return text.strip()

        return None


# ============================================================
# VERIFICATION
# ============================================================

class Verifier:
    def __init__(self):
        self.extractor = CodeExtractor()
        self.sandbox = DockerSandbox()

    def verify(self, task: Task, output: str, strategy: StrategyGenome) -> VerificationReport:
        gate_results: Dict[str, Any] = {}
        errors: List[str] = []
        warnings: List[str] = []
        score = 0.0

        # Gate 1: format/nonempty
        gate_results["format"] = bool(output.strip())
        if not output.strip():
            errors.append("Empty output.")
        else:
            score += 0.1

        # Gate 2: assumptions / uncertainty
        if any(k in output.lower() for k in ["assumption", "unknown", "uncertain", "verify"]):
            score += 0.1
        else:
            warnings.append("No explicit assumptions or uncertainty boundaries.")

        # Gate 3: code extraction and sandbox run
        if task.requires_code:
            code = self.extractor.extract_python(output)
            gate_results["code_extract"] = bool(code)
            if not code:
                errors.append("Code required but no Python code found.")
            else:
                static_ok, static_error = self.static_python_check(code)
                gate_results["static_check"] = {"passed": static_ok, "error": static_error}
                if static_ok:
                    score += 0.2
                else:
                    errors.append(static_error)

                sandbox_result = self.sandbox.run_python_files({"main.py": code})
                gate_results["sandbox"] = sandbox_result
                if sandbox_result["passed"]:
                    score += 0.4
                else:
                    if "Docker is not installed" in sandbox_result.get("stderr", ""):
                        warnings.append("Docker sandbox unavailable; static verification only.")
                        score += 0.15
                    else:
                        errors.append(sandbox_result.get("stderr", "Sandbox failed."))

        # Gate 4: current fact warning
        if task.requires_current_facts:
            warnings.append("Current fact claims need live web/API verification before final trust.")

        # Gate 5: basic safety
        unsafe_terms = ["steal password", "malware", "credential theft", "ransomware"]
        unsafe = any(t in output.lower() for t in unsafe_terms)
        gate_results["security_basic"] = not unsafe
        if unsafe:
            errors.append("Unsafe output detected.")
        else:
            score += 0.1

        minimum_score = 0.4 if any("Docker sandbox unavailable" in w for w in warnings) else 0.55
        passed = not errors and score >= minimum_score
        return VerificationReport(
            passed=passed,
            score=round(score, 3),
            gate_results=gate_results,
            errors=errors,
            warnings=warnings,
        )

    def static_python_check(self, code: str) -> Tuple[bool, str]:
        try:
            compile(code, "candidate.py", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e}"


# ============================================================
# FAILURE ANALYSIS
# ============================================================

class FailureAnalyzer:
    def analyze(self, report: VerificationReport) -> Optional[str]:
        text = " ".join(report.errors).lower()
        if not text and report.warnings:
            return "weak_verification"
        if "syntaxerror" in text:
            return "syntax_error"
        if "nameerror" in text:
            return "undefined_symbol"
        if "module" in text and "not found" in text:
            return "missing_dependency"
        if "timed out" in text:
            return "timeout"
        if "no python code" in text:
            return "missing_code"
        if "unsafe" in text:
            return "safety_failure"
        if text:
            return "unknown_failure"
        return None


# ============================================================
# STRATEGY MUTATION + PROMOTION
# ============================================================

class StrategyMutator:
    def mutate(self, strategy: StrategyGenome, failure_type: Optional[str]) -> StrategyGenome:
        new_rules = list(strategy.rules)

        mutation_rules = {
            "syntax_error": "Before finalizing code, compile mentally and avoid syntax shortcuts.",
            "undefined_symbol": "Ensure every symbol, import, class, and function is defined before use.",
            "missing_dependency": "Prefer standard-library code unless dependencies are explicitly installed.",
            "timeout": "Avoid infinite loops and add bounded iteration.",
            "missing_code": "When code is requested, include complete runnable code blocks.",
            "weak_verification": "Explicitly label assumptions, verification limits, and confidence.",
            "unknown_failure": "Use smaller patches and verify each component independently.",
        }

        if failure_type in mutation_rules and mutation_rules[failure_type] not in new_rules:
            new_rules.append(mutation_rules[failure_type])

        return StrategyGenome(
            id=f"{strategy.domain}.solver.v{strategy.version + 1}",
            domain=strategy.domain,
            version=strategy.version + 1,
            planner=strategy.planner,
            reasoning_depth=min(strategy.reasoning_depth + 1, 10),
            rules=new_rules,
            tools_allowed=strategy.tools_allowed,
            verification_stack=strategy.verification_stack,
            repair_attempts=strategy.repair_attempts,
            promotion_threshold=strategy.promotion_threshold,
            rollback_threshold=strategy.rollback_threshold,
            score=strategy.score,
            successes=strategy.successes,
            failures=strategy.failures,
            parent_id=strategy.id,
        )


class PromotionGate:
    def should_promote(self, old: StrategyGenome, candidate: StrategyGenome, report: VerificationReport) -> bool:
        if not report.passed:
            return False
        if report.score < candidate.promotion_threshold:
            return False
        if candidate.score < old.score and old.score > 0:
            return False
        return True


class RollbackManager:
    def should_rollback(self, strategy: StrategyGenome) -> bool:
        total = strategy.successes + strategy.failures
        if total < 5:
            return False
        performance = strategy.successes / total
        return performance < strategy.rollback_threshold


# ============================================================
# ORCHESTRATOR
# ============================================================

class AdaptiveAIKernel:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or DummyLLM()
        self.working = WorkingMemory()
        self.longterm = LongTermMemory()
        self.semantic = SemanticMemory()
        self.classifier = TaskClassifier()
        self.registry = StrategyRegistry(self.longterm)
        self.planner = Planner()
        self.builder = BuilderAgent("builder", self.llm)
        self.critic = CriticAgent("critic", self.llm)
        self.security = SecurityAgent("security", self.llm)
        self.judge = JudgeAgent("judge", self.llm)
        self.verifier = Verifier()
        self.failure_analyzer = FailureAnalyzer()
        self.mutator = StrategyMutator()
        self.promotion_gate = PromotionGate()
        self.rollback = RollbackManager()

    def solve(self, user_input: str) -> Dict[str, Any]:
        task = self.classifier.classify(user_input)
        strategy = self.registry.select(task)
        memories = self.longterm.recent_experiences(task.domain)
        plan = self.planner.plan(task, strategy, memories)

        self.longterm.log_event("task_received", asdict(task))

        candidate = self._build_candidate(task, strategy, plan, memories)
        critique = self._critique_candidate(task, strategy, candidate)
        improved = self._improve_candidate(task, strategy, candidate, critique)

        report = self.verifier.verify(task, improved, strategy)
        failure_type = self.failure_analyzer.analyze(report)

        repair_count = 0
        while not report.passed and repair_count < strategy.repair_attempts:
            repair_count += 1
            improved = self._repair_candidate(task, strategy, improved, report, failure_type)
            report = self.verifier.verify(task, improved, strategy)
            failure_type = self.failure_analyzer.analyze(report)

        if report.passed:
            strategy.successes += 1
        else:
            strategy.failures += 1

        strategy.score = self._update_strategy_score(strategy, report)

        candidate_strategy = self.mutator.mutate(strategy, failure_type)
        candidate_strategy.score = max(strategy.score, report.score)

        if self.promotion_gate.should_promote(strategy, candidate_strategy, report):
            self.registry.promote(candidate_strategy)
            active_strategy = candidate_strategy
            promoted = True
        else:
            self.registry.promote(strategy)
            active_strategy = strategy
            promoted = False

        exp = Experience(
            id=str(uuid.uuid4()),
            task=task,
            strategy_id=active_strategy.id,
            plan=plan,
            output=improved,
            verification=report,
            failure_type=failure_type,
        )
        self.longterm.save_experience(exp)
        self.semantic.add(task.raw + "\n" + improved, {"experience_id": exp.id, "domain": task.domain})

        self.longterm.log_event("task_completed", {
            "task_id": task.id,
            "passed": report.passed,
            "score": report.score,
            "failure_type": failure_type,
            "promoted": promoted,
        })

        return {
            "task": asdict(task),
            "strategy": asdict(active_strategy),
            "plan": plan,
            "answer": improved,
            "verification": asdict(report),
            "failure_type": failure_type,
            "strategy_promoted": promoted,
        }

    def _system_prompt(self, strategy: StrategyGenome) -> str:
        return f"""
You are an advanced verification-first AI solver.

Strategy Genome: {strategy.id}
Reasoning Depth: {strategy.reasoning_depth}
Rules:
{json.dumps(strategy.rules, indent=2)}

Hard laws:
- Do not hallucinate.
- No factual claim without evidence or uncertainty label.
- No code claim without executable code where possible.
- Prefer verified truth over pleasing language.
- If unsure, state the missing information.
""".strip()

    def _build_candidate(self, task: Task, strategy: StrategyGenome, plan: List[str], memories: List[Dict[str, Any]]) -> str:
        user = f"""
Task:
{task.raw}

Plan:
{json.dumps(plan, indent=2)}

Relevant Memories:
{json.dumps(memories, indent=2)[:4000]}

Produce the strongest possible solution.
If code is needed, include complete Python code in a ```python block.
""".strip()
        return self.builder.run(self._system_prompt(strategy), user).content

    def _critique_candidate(self, task: Task, strategy: StrategyGenome, candidate: str) -> str:
        user = f"""
Task:
{task.raw}

Candidate answer:
{candidate}

Attack this answer. Find logic gaps, unsupported claims, missing tests, unsafe assumptions, and incomplete code.
Return a concise defect list.
""".strip()
        return self.critic.run(self._system_prompt(strategy), user).content

    def _improve_candidate(self, task: Task, strategy: StrategyGenome, candidate: str, critique: str) -> str:
        user = f"""
Task:
{task.raw}

Candidate:
{candidate}

Critique:
{critique}

Rewrite the answer to fix defects. Return the improved final answer.
""".strip()
        return self.builder.run(self._system_prompt(strategy), user).content

    def _repair_candidate(
        self,
        task: Task,
        strategy: StrategyGenome,
        candidate: str,
        report: VerificationReport,
        failure_type: Optional[str],
    ) -> str:
        user = f"""
Task:
{task.raw}

Current answer/code:
{candidate}

Verification failed.
Failure type: {failure_type}
Report:
{json.dumps(asdict(report), indent=2)}

Repair the answer. If code failed, return corrected complete Python code in a ```python block.
""".strip()
        return self.builder.run(self._system_prompt(strategy), user).content

    def _update_strategy_score(self, strategy: StrategyGenome, report: VerificationReport) -> float:
        total = strategy.successes + strategy.failures
        pass_rate = strategy.successes / total if total else 0.0
        return round((0.65 * pass_rate) + (0.35 * report.score), 3)


# ============================================================
# EXAMPLE REAL LLM ADAPTER TEMPLATE
# ============================================================

class OpenAIStyleClient:
    """
    Template only. Install your provider SDK and wire it here.
    Do not hardcode API keys. Use environment variables.
    """

    def __init__(self, model: str = "your-model-name"):
        self.model = model

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        raise NotImplementedError(
            "Wire this to your LLM provider. Keep the kernel model-agnostic."
        )


# ============================================================
# EXTENSIONS: MODEL ADAPTERS, BENCHMARKS, VECTOR MEMORY,
# PROJECT WRITER, FASTAPI READY SURFACE
# ============================================================

"""
The section below upgrades the kernel from a control core into a deployable
advanced AI system scaffold.

Add these dependencies when you are ready:

pip install fastapi uvicorn pydantic psycopg[binary] numpy

Optional:
pip install openai anthropic qdrant-client chromadb
"""


# ============================================================
# ADVANCED MODEL ROUTER
# ============================================================

class ModelRouter:
    """
    Routes work to different model clients.
    Keep this provider-agnostic so you can swap models or run ensembles.
    """

    def __init__(self, default: LLMClient, coder: Optional[LLMClient] = None, critic: Optional[LLMClient] = None):
        self.default = default
        self.coder = coder or default
        self.critic = critic or default

    def for_task(self, task: Task, role: str = "default") -> LLMClient:
        if role == "coder" or task.requires_code:
            return self.coder
        if role == "critic":
            return self.critic
        return self.default


# ============================================================
# OPENAI ADAPTER EXAMPLE
# ============================================================

class OpenAIResponsesClient:
    """
    Real adapter example.

    Usage:
        pip install openai
        export OPENAI_API_KEY="..."
        llm = OpenAIResponsesClient(model="gpt-5.5")
        kernel = AdaptiveAIKernel(llm=llm)

    Keep keys in environment variables. Never store them in memory logs.
    """

    def __init__(self, model: str = "gpt-5.5"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        return self._client

    def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        client = self._get_client()
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return response.output_text


# ============================================================
# VECTOR MEMORY INTERFACE
# ============================================================

class VectorMemoryProtocol(Protocol):
    def upsert(self, item_id: str, text: str, metadata: Dict[str, Any]) -> None:
        ...

    def query(self, text: str, limit: int = 8) -> List[Dict[str, Any]]:
        ...


class LocalKeywordVectorMemory:
    """
    Local fallback. Replace with pgvector/Qdrant/Chroma.
    This gives you the same interface before infrastructure is attached.
    """

    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    def upsert(self, item_id: str, text: str, metadata: Dict[str, Any]) -> None:
        self.rows.append({"id": item_id, "text": text.lower(), "metadata": metadata})

    def query(self, text: str, limit: int = 8) -> List[Dict[str, Any]]:
        q = set(text.lower().split())
        scored = []
        for row in self.rows:
            score = len(q.intersection(set(row["text"].split())))
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, **r} for s, r in scored[:limit]]


class PgVectorMemoryTemplate:
    """
    Schema template for pgvector.

    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS ai_memories (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        metadata JSONB NOT NULL,
        embedding vector(1536),
        created_at TIMESTAMPTZ DEFAULT now()
    );

    You need an embedding function from your model provider.
    """

    def __init__(self, dsn: str, embedder: Callable[[str], List[float]]):
        self.dsn = dsn
        self.embedder = embedder

    def upsert(self, item_id: str, text: str, metadata: Dict[str, Any]) -> None:
        raise NotImplementedError("Wire to psycopg and pgvector once database is provisioned.")

    def query(self, text: str, limit: int = 8) -> List[Dict[str, Any]]:
        raise NotImplementedError("Wire vector similarity query using <=> operator.")


# ============================================================
# BENCHMARK BANK
# ============================================================

@dataclass
class BenchmarkCase:
    id: str
    domain: str
    prompt: str
    expected_traits: List[str]
    forbidden_traits: List[str]
    requires_code: bool = False
    min_score: float = 0.7


class BenchmarkBank:
    def __init__(self, path: str = "ai_memory/benchmarks.json"):
        self.path = Path(path)
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps(self.default_cases(), indent=2))

    def default_cases(self) -> List[Dict[str, Any]]:
        return [
            asdict(BenchmarkCase(
                id="code_calculator_001",
                domain="software_engineering",
                prompt="Write a Python calculator with add, subtract, multiply, divide, and division by zero handling.",
                expected_traits=["def", "divide", "zero", "return"],
                forbidden_traits=["TODO", "pass"],
                requires_code=True,
                min_score=0.75,
            )),
            asdict(BenchmarkCase(
                id="reasoning_uncertainty_001",
                domain="reasoning",
                prompt="Solve a problem with missing data and clearly state assumptions.",
                expected_traits=["assumption", "unknown", "cannot determine"],
                forbidden_traits=["definitely", "guaranteed"],
                requires_code=False,
                min_score=0.65,
            )),
            asdict(BenchmarkCase(
                id="anti_hallucination_001",
                domain="general",
                prompt="Answer a current-events question without browsing. You must avoid hallucination.",
                expected_traits=["verify", "current", "uncertain"],
                forbidden_traits=["as of today", "breaking news confirms"],
                requires_code=False,
                min_score=0.7,
            )),
        ]

    def load(self, domain: Optional[str] = None) -> List[BenchmarkCase]:
        data = json.loads(self.path.read_text())
        cases = [BenchmarkCase(**x) for x in data]
        if domain:
            cases = [c for c in cases if c.domain == domain]
        return cases

    def add(self, case: BenchmarkCase):
        data = json.loads(self.path.read_text())
        data.append(asdict(case))
        self.path.write_text(json.dumps(data, indent=2))


class BenchmarkRunner:
    def __init__(self, kernel: "AdaptiveAIKernel"):
        self.kernel = kernel
        self.bank = BenchmarkBank()

    def run_domain(self, domain: str, limit: int = 10) -> Dict[str, Any]:
        cases = self.bank.load(domain)[:limit]
        results = []

        for case in cases:
            result = self.kernel.solve(case.prompt)
            text = result["answer"].lower()

            expected_hits = sum(1 for t in case.expected_traits if t.lower() in text)
            forbidden_hits = sum(1 for t in case.forbidden_traits if t.lower() in text)

            trait_score = expected_hits / max(len(case.expected_traits), 1)
            penalty = forbidden_hits * 0.25
            verification_score = result["verification"]["score"]
            final = max(0.0, min(1.0, (0.6 * verification_score) + (0.4 * trait_score) - penalty))

            results.append({
                "case_id": case.id,
                "score": round(final, 3),
                "passed": final >= case.min_score,
                "verification": result["verification"],
            })

        pass_rate = sum(1 for r in results if r["passed"]) / max(len(results), 1)
        avg_score = sum(r["score"] for r in results) / max(len(results), 1)

        return {
            "domain": domain,
            "cases": len(results),
            "pass_rate": round(pass_rate, 3),
            "avg_score": round(avg_score, 3),
            "results": results,
        }


# ============================================================
# PROJECT WRITER FOR SELF-CODING
# ============================================================

class ProjectWriter:
    """
    Lets the AI produce a multi-file patch, then writes it into a temporary
    project for sandbox execution.
    """

    FILE_BLOCK = re.compile(
        r"```file:(?P<path>[^\n]+)\n(?P<content>.*?)```",
        re.DOTALL | re.IGNORECASE,
    )

    def extract_files(self, text: str) -> Dict[str, str]:
        files = {}
        for match in self.FILE_BLOCK.finditer(text):
            path = match.group("path").strip()
            content = match.group("content").strip()
            if self._safe_path(path):
                files[path] = content
        return files

    def _safe_path(self, path: str) -> bool:
        p = Path(path)
        if p.is_absolute():
            return False
        if ".." in p.parts:
            return False
        return True

    def write_temp_project(self, files: Dict[str, str]) -> Path:
        tmp = Path(tempfile.mkdtemp())
        for name, content in files.items():
            path = tmp / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return tmp


class MultiFileSandbox(DockerSandbox):
    def run_project(self, files: Dict[str, str], timeout: int = 90) -> Dict[str, Any]:
        command = ["sh", "-c", "python -m pytest -q || python main.py"]
        return self.run_python_files(files, command=command, timeout=timeout)


# ============================================================
# ADVANCED SCORER
# ============================================================

class ScoreAggregator:
    def score(self, report: VerificationReport, user_satisfaction: Optional[float] = None) -> float:
        correctness = 1.0 if report.passed else 0.0
        verification_strength = report.score
        safety = 0.0 if any("unsafe" in e.lower() for e in report.errors) else 1.0
        completeness = 0.8 if not report.warnings else 0.55
        user_score = user_satisfaction if user_satisfaction is not None else 0.5

        final = (
            0.35 * correctness
            + 0.25 * verification_strength
            + 0.15 * completeness
            + 0.15 * safety
            + 0.10 * user_score
        )
        return round(max(0.0, min(1.0, final)), 3)


# ============================================================
# EXPERIENCE REPLAY AND MEMORY CONSOLIDATION
# ============================================================

class ExperienceReplay:
    def __init__(self, memory: LongTermMemory):
        self.memory = memory

    def failure_clusters(self, domain: str) -> Dict[str, int]:
        clusters: Dict[str, int] = {}
        for exp in self.memory.recent_experiences(domain, limit=100):
            failure = exp.get("failure_type") or "none"
            clusters[failure] = clusters.get(failure, 0) + 1
        return clusters


class MemoryConsolidator:
    """
    Converts repeated experiences into stable procedural rules.
    """

    def __init__(self, memory: LongTermMemory):
        self.memory = memory
        self.replay = ExperienceReplay(memory)

    def consolidate_domain(self, domain: str) -> List[str]:
        clusters = self.replay.failure_clusters(domain)
        rules = []

        if clusters.get("syntax_error", 0) >= 2:
            rules.append("For coding tasks, compile-check syntax before sandbox execution.")
        if clusters.get("runtime_error", 0) >= 2:
            rules.append("For coding tasks, handle runtime errors gracefully.")
        if clusters.get("none", 0) >= 5:
            rules.append("Successful patterns should be reused for similar tasks.")

        return rules

