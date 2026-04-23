from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .utils import call_openai_text, call_openai_json
from .schemas import AttemptTrace, QAExample, JudgeResult, ReflectionEntry, RunRecord

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        for attempt_id in range(1, self.max_attempts + 1):
            # 1. Gọi hệ thống Actor giải quyết câu hỏi
            actor_context = "\n".join([f"[{c.title}] {c.text}" for c in example.context])
            actor_user = f"Context:\n{actor_context}\n\nQuestion: {example.question}\n\n"
            if reflection_memory:
                actor_user += "Reflection Memory (Advice):\n" + "\n".join(reflection_memory) + "\n\n"
            actor_user += "Answer concisely:"
            
            answer, tok_act, lat_act = call_openai_text(ACTOR_SYSTEM, actor_user)
            
            # 2. Gọi hệ thống Teacher chấm điểm
            eval_user = f"Question: {example.question}\nGold Answer: {example.gold_answer}\nPredicted Answer: {answer}"
            judge, tok_eval, lat_eval = call_openai_json(EVALUATOR_SYSTEM, eval_user, JudgeResult)
            
            token_estimate = tok_act + tok_eval
            latency_ms = lat_act + lat_eval
            final_answer = answer
            final_score = judge.score
            
            # 3. Kích hoạt Reflexion rút kinh nghiệm (Nếu sai & vẫn còn mạng)
            if final_score == 0 and self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                ref_user = f"Question: {example.question}\nFailed Answer: {answer}\nEvaluator Critique: {judge.reason}"
                ref_obj, tok_ref, lat_ref = call_openai_json(REFLECTOR_SYSTEM, ref_user, ReflectionEntry)
                ref_obj.attempt_id = attempt_id
                
                reflection_memory.append(ref_obj.strategy)
                reflections.append(ref_obj)
                
                token_estimate += tok_ref
                latency_ms += lat_ref
            
            # Lưu vết
            trace = AttemptTrace(
                attempt_id=attempt_id, answer=answer, score=judge.score, 
                reason=judge.reason, token_estimate=token_estimate, latency_ms=latency_ms
            )
            traces.append(trace)
            
            if final_score == 1:
                break
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        
        # Mở rộng chuẩn hóa logic bắt các Failure Modes thay cho Mock ID
        if final_score == 1:
            failure_mode = "none"
        elif self.agent_type == "reflexion" and len(traces) == self.max_attempts and len(set(t.answer for t in traces)) == 1:
            failure_mode = "looping"
        elif "and" in final_answer or "," in final_answer:
            failure_mode = "entity_drift"
        else:
            failure_mode = "wrong_final_answer"
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(agent_type="react", max_attempts=1)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts)

class LatsAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, branch_factor: int = 3) -> None:
        super().__init__(agent_type="mini_lats_branching", max_attempts=max_attempts)
        self.branch_factor = branch_factor

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0
        total_tokens = 0
        total_latency = 0
        
        for attempt_id in range(1, self.max_attempts + 1):
            actor_context = "\n".join([f"[{c.title}] {c.text}" for c in example.context])
            actor_user = f"Context:\n{actor_context}\n\nQuestion: {example.question}\n\n"
            if reflection_memory:
                actor_user += "Reflection Memory (Advice):\n" + "\n".join(reflection_memory) + "\n\n"
            actor_user += "Answer concisely:"
            
            # 1. Mở nhánh (Branching)
            branch_answers = []
            for _ in range(self.branch_factor):
                ans, tok_act, lat_act = call_openai_text(ACTOR_SYSTEM, actor_user, temperature=0.7)
                total_tokens += tok_act
                total_latency += lat_act
                branch_answers.append(ans)
                
            # 2. Định giá (Value)
            best_answer = branch_answers[0]
            best_score = 0
            best_reason = ""
            all_reasons = []
            
            for ans in branch_answers:
                eval_user = f"Question: {example.question}\nGold Answer: {example.gold_answer}\nPredicted Answer: {ans}"
                judge, tok_eval, lat_eval = call_openai_json(EVALUATOR_SYSTEM, eval_user, JudgeResult)
                total_tokens += tok_eval
                total_latency += lat_eval
                
                all_reasons.append(f"Answer: {ans} -> Critique: {judge.reason}")
                if judge.score > best_score:
                    best_score = judge.score
                    best_answer = ans
                    best_reason = judge.reason
                elif best_score == 0:
                    best_answer = ans
                    best_reason = judge.reason
                    
                if best_score == 1:
                    break
                    
            final_answer = best_answer
            final_score = best_score
            
            # Lưu vết
            trace = AttemptTrace(
                attempt_id=attempt_id, answer=best_answer, score=best_score, 
                reason=best_reason, token_estimate=total_tokens, latency_ms=total_latency
            )
            traces.append(trace)
            if final_score == 1:
                break
                
            # 3. Suy ngẫm nếu tất cả nhánh đều sai
            if attempt_id < self.max_attempts:
                ref_user = f"Question: {example.question}\nFailed Branches:\n" + "\n".join(all_reasons)
                ref_obj, tok_ref, lat_ref = call_openai_json(REFLECTOR_SYSTEM, ref_user, ReflectionEntry)
                ref_obj.attempt_id = attempt_id
                reflection_memory.append(ref_obj.strategy)
                reflections.append(ref_obj)
                total_tokens += tok_ref
                total_latency += lat_ref
                
        if final_score == 1:
            failure_mode = "none"
        elif len(traces) == self.max_attempts and len(set(t.answer for t in traces)) == 1:
            failure_mode = "looping"
        elif "and" in final_answer or "," in final_answer:
            failure_mode = "entity_drift"
        else:
            failure_mode = "wrong_final_answer"
            
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)
