from pathlib import Path
import json
from hashlib import md5


class Prompt:
    def __init__(self, prompt):
        self.prompt = prompt
        self.adjusted_prompt = None
        self.key = md5(self.prompt.encode()).hexdigest()
        self.feedbacks = []

    def add_feedback(self, llm_output, feedback):
        self.feedbacks.append({"llm_output": llm_output, "feedback": feedback})

    def dict(self):
        return {"prompt": self.prompt, "feedback": self.feedbacks}


class FeedbackRegistry:

    def __init__(self):
        self.logs: dict = {}
        self.collect_feedback: bool = False

    def add(self, prompt: Prompt, llm_response: str, feedback: dict):
        key = prompt.key
        prompt.add_feedback(llm_response, feedback["feedback"])
        self.logs[prompt.key] = prompt.dict()

    def dump(self, basepath: Path):
        filepath: Path = basepath / "feedback_log.json"
        with filepath.open("w") as file:
            json.dump(self.logs, file, indent=2)


def store_feedback(prompt: Prompt, llm_output: str, feedback: dict):
    # Store the feedback in a structured format
    FEEDBACK_REGISTRY.add(prompt, llm_output, feedback)


def collect_feedback(llm_output: str) -> dict:
    # Simulate collecting feedback from the user
    is_correct = input(f"Was the LLM output correct? (yes/no): ").lower() == 'yes'
    feedback = None
    if not is_correct:
        feedback = input("Please provide corrections or suggestions: ")
    return {"is_correct": is_correct, "feedback": feedback}


def adjust_llm_prompt(prompt: Prompt, llm_response: str, feedback: dict, ):
    if not feedback["is_correct"]:
        # Adjust the prompt to include user corrections or suggestions
        feedbacks = "\n".join([
            f"""
            ### Response {idx + 1}:
            ----------------
            {resp["llm_output"]}

            ### User feedback on your response {idx + 1}:
            ------------------------------------
            {resp["feedback"]}
            """
            for idx, resp in enumerate(prompt.feedbacks[:-1])
        ])
        historical_feedbacks = ""
        if feedbacks:
            historical_feedbacks = f"""
        ## Your Responses and feedbacks:
        --------------------------------
            {feedbacks}
        
            ### Based on earlier feedbacks, your response is:
            -------------------------------------------------
            {llm_response}
            """
        else:
            historical_feedbacks = f"""
        ## Your response for user request is:
        -------------------------------------
        {llm_response}
            """

        corrected_prompt = f"""
        Adjust the your response considering user's current feedback.

        ## User Query:
        --------------
        {prompt.prompt}
        {historical_feedbacks}
        ## User's has following feedback to be incorporated:
        ---------------------------------------------------
        {feedback["feedback"]}
        """
        return corrected_prompt


def llm_feedback_loop(prompt: Prompt, llm_response: str):
    if not FEEDBACK_REGISTRY.collect_feedback:
        return 0
    # Step 1: Initial GPT-3 response
    print(f"""
    {"*" * 100}
    Review LLM's response: 
    ----------------------
    
    ## User Query:
    --------------

    {prompt.prompt}
    
    ## LLM Response{f" (based on your recent feedback)" if prompt.feedbacks else ""}:
    ----------------

    {llm_response}

    {"*" * 100}
    """.replace('\\n', '\n').replace('\\\\"', '"'))

    # Step 2: Collect feedback from the user
    feedback = collect_feedback(llm_response)

    # Step 3: Store the feedback
    store_feedback(prompt, llm_response, feedback)

    # Step 4: If necessary, re-run GPT-3 with the adjusted prompt
    if not feedback["is_correct"]:
        # Step 5: Adjust LLM's next prompt
        prompt.adjusted_prompt = adjust_llm_prompt(prompt, llm_response, feedback)
    else:
        prompt.adjusted_prompt = None


# Feedback registry instance
FEEDBACK_REGISTRY = FeedbackRegistry()
