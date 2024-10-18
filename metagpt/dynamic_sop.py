#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dynamically generates SOP (Standard Operating Procedure) and allocates agents based on the project idea.
"""

from __future__ import annotations
import os
import ast
import asyncio
import sys

from metagpt.config2 import config
from metagpt.context import Context
from metagpt.provider.llm_provider_registry import create_llm_instance
from metagpt.roles import Role
from metagpt.logs import logger
import re
import importlib.util
from metagpt.utils.feedback_collector import llm_feedback_loop, Prompt



class RoleInspector:
    def __init__(self, output_file=None):

        self.directory = self.get_role_directory()
        self.output_file = output_file

    def get_role_directory(self):
        # Load the metagpt module
        module_name = 'metagpt.roles'
        spec = importlib.util.find_spec(module_name)
        
        if spec is None:
            raise ImportError(f"Module '{module_name}' could not be found.")
        
        # Get the directory where the roles module is located
        role_directory = os.path.dirname(spec.origin)
        
        return role_directory

    def is_role_class(self, node):
        return any(base.id == 'Role' for base in node.bases if isinstance(base, ast.Name))

    # Function to extract the 'goal' and 'desc' attributes from class type annotations and assignments
    def get_class_attributes(self, node):
        goal, desc = None, None

        # Check for attribute annotations (type hints)
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                attr_name = stmt.target.id
                if attr_name == 'goal' and isinstance(stmt.value, ast.Constant) and stmt.value.value:
                    goal = stmt.value.value
                if attr_name == 'desc' and isinstance(stmt.value, ast.Constant) and stmt.value.value:
                    desc = stmt.value.value

            # Check for normal assignments
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        if target.id == 'goal' and isinstance(stmt.value, ast.Constant) and stmt.value.value:
                            goal = stmt.value.value
                        if target.id == 'desc' and isinstance(stmt.value, ast.Constant) and stmt.value.value:
                            desc = stmt.value.value
                      
        return goal or desc
    
    # Function to extract actions from the method call: self.set_actions([PrepareDocuments, WritePRD])
    def get_actions(self, node):
        actions = []
        watches = []

        # Traverse the body of the class definition
        for stmt in node.body:
            # Check if the statement is a function definition
            if isinstance(stmt, ast.FunctionDef):
                # Traverse the body of the function to find calls
                for func_stmt in stmt.body:
                    line_number = func_stmt.lineno

                    # Check for expressions
                    if isinstance(func_stmt, ast.Expr):
                        stmt_value_type = type(func_stmt.value)

                        if stmt_value_type == ast.Call:
                            # Handle set_actions
                            if isinstance(func_stmt.value.func, ast.Attribute) and func_stmt.value.func.attr == 'set_actions':
                                if func_stmt.value.args:
                                    if isinstance(func_stmt.value.args[0], (ast.List, ast.Set)):
                                        for element in func_stmt.value.args[0].elts:
                                            if isinstance(element, ast.Name):
                                                actions.append(element.id)
                                    elif isinstance(func_stmt.value.args[0], ast.Call):
                                        if isinstance(func_stmt.value.args[0].func, ast.Name):
                                            actions.append(func_stmt.value.args[0].func.id)

                            # Handle _watch
                            if isinstance(func_stmt.value.func, ast.Attribute) and func_stmt.value.func.attr == '_watch':
                                if func_stmt.value.args:
                                    if isinstance(func_stmt.value.args[0], (ast.List, ast.Set)):
                                        for element in func_stmt.value.args[0].elts:
                                            if isinstance(element, ast.Name):
                                                watches.append(element.id)

                    # Check for conditional actions
                    elif isinstance(func_stmt, ast.If):
                        for if_stmt in func_stmt.body:
                            if isinstance(if_stmt, ast.Expr) and isinstance(if_stmt.value, ast.Call):
                                if isinstance(if_stmt.value.func, ast.Attribute) and if_stmt.value.func.attr == 'set_actions':
                                    if if_stmt.value.args:
                                        if isinstance(if_stmt.value.args[0], (ast.List, ast.Set)):
                                            for element in if_stmt.value.args[0].elts:
                                                if isinstance(element, ast.Name):
                                                    actions.append(element.id)
                                        elif isinstance(if_stmt.value.args[0], ast.Call):
                                            if isinstance(if_stmt.value.args[0].func, ast.Name):
                                                actions.append(if_stmt.value.args[0].func.id)

        return actions, watches

    def get_actions2(self, node):
        actions = []
        watches = []

        # Traverse the body of the class definition
        for stmt in node.body:
            # Check if the statement is a function definition
            if isinstance(stmt, ast.FunctionDef):
                # Traverse the body of the function to find calls
                for func_stmt in stmt.body:
                    # Print the actual line of the current statement
                    line_number = func_stmt.lineno
                    # print(f"Processing line {line_number}: {ast.get_source_segment(code, func_stmt)}")

                    # Check for expressions
                    if isinstance(func_stmt, ast.Expr):
                        # Print the type of func_stmt.value
                        stmt_value_type = type(func_stmt.value)
                        # print(f"The type of stmt.value is: {stmt_value_type}")

                        if stmt_value_type == ast.Call:
                            # Check if it's the set_actions call
                            if isinstance(func_stmt.value.func, ast.Attribute) and func_stmt.value.func.attr == 'set_actions':
                                # print(f"Found set_actions: {ast.dump(func_stmt)}")  # Debugging print
                                if func_stmt.value.args and isinstance(func_stmt.value.args[0], ast.List):
                                    for element in func_stmt.value.args[0].elts:
                                        if isinstance(element, ast.Name):
                                            actions.append(element.id)  # Extract the name of the action
                            # Check if it's the watch call
                            if isinstance(func_stmt.value.func, ast.Attribute) and func_stmt.value.func.attr == '_watch':
                                if func_stmt.value.args and isinstance(func_stmt.value.args[0], ast.List):
                                    for element in func_stmt.value.args[0].elts:
                                        if isinstance(element, ast.Name):
                                            watches.append(element.id)  # Extract the name of the action

                    # If it's a call statement, handle it
                    elif isinstance(func_stmt, ast.Assign):
                        for target in func_stmt.targets:
                            if isinstance(target, ast.Name) and target.id == 'actions':
                                # You can add logic here if you want to fetch actions assigned directly
                                pass

        # print(f"Actions found: {actions}")
        return actions, watches

    def process_file(self, file_path):
        with open(file_path, 'r') as file:
            file_content = file.read()

        tree = ast.parse(file_content)
        role_classes = []
        file_name = os.path.basename(file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self.is_role_class(node):
                skill = self.get_class_attributes(node)
                actions, watches = self.get_actions(node)
                agent = {'agent':node.name, 'skill': skill, 'action':actions, 'watch':watches, 'file_name':file_name}

                role_classes.append(agent)
                    
        return role_classes

    def get_all_role_summary(self):
        role_class_data = []
        for root, _, files in os.walk(self.directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    role_class_data.extend(self.process_file(file_path))
        return role_class_data

    def save_role_summary(self, role_class_data):
        if self.output_file:
            with open(self.output_file, 'w') as summary_file:
                for role_class in role_class_data:
                    for k, v in role_class.items():
                        summary_file.write(f"{k}: {v}\n")
                    summary_file.write("\n")
            print(f"Role summary saved to {self.output_file}")

class DynamicSOP:
    SUPPORTED_DOMAINS = ['software engineering']  # Replace with MetaGPT-defined supported domains

    def __init__(self, context):
        self.context = context
        self.llm = create_llm_instance(self.context.config.llm)
        self.inspector = RoleInspector()
        self.agents = self.inspector.get_all_role_summary()

    async def classify_idea(self, idea: str | Prompt) -> str:
        if not isinstance(idea, Prompt):
            idea = Prompt(f"""
            You are given a task description and a list of supported domains: {self.SUPPORTED_DOMAINS}.
            Classify the task to one of the domains based on key features or keywords.
            
            Task: {idea}

            Important:
            - Only return the domain name do not include any additional text or explanations.

            ### Output format:
            <Domain name> (exact match to one of '{self.SUPPORTED_DOMAINS}', otherwise return the domain/sector the task belongs to.)
            """)
        query = idea.adjusted_prompt if idea.adjusted_prompt else idea.prompt
        domain = await self.llm.aask(query, stream=False)
        llm_feedback_loop(idea, domain)
        if idea.adjusted_prompt:
            domain = await self.classify_idea(idea)
        self.domain = domain.strip()
        return self.domain
    
    def get_all_agents(self, list_of_agents):
        agent_dict = {}
        for item in list_of_agents:
            agent = item['agent']
            # Create a dictionary for each agent with the rest of the values
            agent_dict[agent] = {
                'skill': item['skill'],
                'action': item['action'],
                'watch': item['watch'],
                'file_name': item['file_name']
            }
        
        return agent_dict

    async def assign_agents(self, idea: str | Prompt, domain: str) -> list:
        # starting from those responsible for initiating the project to those handling implementation, testing, or delivery.
        if not isinstance(idea, Prompt):
            json_example = """
            ```json
            [
                {
                    "subtask_number": int,            // <Order of the subtask or requirement>
                    "subtask_description": str,       // <Task Subsection or Requirement>
                    "agent": str,                     // <Agent Name>
                    "skill": str,                     // <Agent Skill>
                    "actions": list[str],             // <Agent Actions>
                    "watch_items": list[str],         // <Agent Watch Items>
                    "trigger": str,                   // <Action that triggers this agent>
                },
                ...
            ]
            ```
            """

            prompt = Prompt(f"""
            Your task is to assign agents to a project based on their skills, actions, and watch items.
            Agents are triggered only when their watch items are updated by the actions of the previous agent. Ensure that all necessary roles are covered in the correct logical sequence, and avoid including agents that are not relevant to the task.
    
            You are given:
    
            A specific task and domain.
            A list of agents, their skills, actions, and watch items.
            Instructions:
                * Identify and match agents to the task based on their skills, actions, and watch items.
                * Only select agents whose watch items are triggered by the actions of a previous agent in the sequence.
                * If no further agent is triggered, stop assigning more agents to the task. This ensures that only the necessary agents are involved.
                * Ensure that no unnecessary agents are included and that agents are logically arranged based on their dependencies.
            Selection Criteria:
                * An agent is only included if their watch items are triggered by the actions of the previous agent.
                * Skip agents if their actions and watch items are not relevant to the task or if no other agent triggers them.
                * If a task can be completed by fewer agents (e.g., only the ProductManager for writing a PRD), include only the relevant agent(s).
            
            Given Task: {idea}
            Domain: {domain}
            Agents: {self.agents}
    
            Output Format: format the output in array of json objects, for example
            {json_example}

            Note:
            Agent: Represents the selected agent for the task.
            Skill: The agent's main competency relevant to the task.
            Actions: The tasks performed by this agent.
            Watch Items: Items that, when updated by another agent’s actions, trigger this agent’s tasks.
            Trigger: The action from the previous agent that triggers this agent.
            """)
        else:
            prompt = idea
        query = prompt.adjusted_prompt if prompt.adjusted_prompt else prompt.prompt
        agents_response = await self.llm.aask(query, stream=True)
        llm_feedback_loop(prompt, agents_response)
        if prompt.adjusted_prompt:
            agents_response = await self.assign_agents(prompt, domain)
        return self.parse_assign_agents2(agents_response)

    def parse_assign_agents2(self, agents_response):
        from metagpt.utils.common import CodeParser
        import json
        agents = json.loads(CodeParser.parse_code(block=None, text=agents_response, lang="json"))
        return agents

    def parse_assign_agents(self, text):
        # Pattern to match steps, agents, skills, actions, watch items, and triggers
        pattern = r'Step\s(\d+):\s([^\n]+)\nAgent:\s([^\n]+)\nSkill:\s([^\n]+)\nActions:\s([^\n]+)\nWatch\sItems:\s([^\n]+)\nTrigger:\s([^\n]+)'

        # Find all matches
        matches = re.findall(pattern, text)

        # Store parsed data
        agent_steps = []
        
        for match in matches:
            step_data = {
                'subtask_number': match[0].strip(),
                'subtask_description': match[1].strip(),
                'agent': match[2].strip(),
                'skill': match[3].strip(),
                'actions': match[4].strip().split(', '),
                'watch_items': match[5].strip().split(', '),
                'trigger': match[6].strip()
            }
            agent_steps.append(step_data)
        
        return agent_steps
        

    def parse_assign_agents_old(self, text):
        # Pattern to match steps, roles, responsibilities, and tasks
        pattern = r'(\d+)\.\s+Step:\s+([^\n]+)\n([A-Za-z]+):\s+([^:]+):\s+([^\n]+)'
        
        # Find all matches
        matches = re.findall(pattern, text)

        subtask_roles_and_responsibilities = []
        
        for match in matches:
            subtask_data = {
                'subtask_number': match[0].strip(),
                'subtask_description': match[1].strip(),
                'agent': match[2].strip(),
                'skill': match[3].strip(),
                'actions': match[4].strip().split(', '),
                'watch': match[5].strip().split(', ')
            }
            subtask_roles_and_responsibilities.append(subtask_data)
        
        return subtask_roles_and_responsibilities
    
    def agg_agents(self, agents):
        final_agents = {}
        for item in agents:
            if item['agent'] in final_agents.keys():
                final_agents[item['agent']]['subtask_description'] += f". {item['subtask_description']}"
            else:
                final_agents[item['agent']] = item
        return final_agents

    def load_agents(self, req_agents):
        instances = []
        if "QaEngineer" in req_agents.keys():
            use_code_review = True
        else:
            use_code_review = False
        
        all_agents = self.get_all_agents(self.agents)
        self.all_agents = all_agents
        
        for agent_class, agent_profile in req_agents.items():
            agent_file = all_agents[agent_class]['file_name'].split('.py')[0]
            # Dynamically import the module from metagpt.roles
            module_name = f'metagpt.roles.{agent_file}'
            module = importlib.import_module(module_name)

            # Get the class from the imported module
            agent = getattr(module, agent_class)
            if  agent_class == 'Engineer':
                instance = agent(n_borg=5, use_code_review=use_code_review)
            else:
                instance = agent()
            instances.append(instance)
        return instances

    async def generate_dynamic_sop(self, idea: str):
        domain = await self.classify_idea(idea)
        self.domain = domain
        if domain != 'None':
            logger.info(f"Given idea '{idea}' is classified under domain '{self.domain}'")
        if domain in self.SUPPORTED_DOMAINS:
            self.req_agents = await self.assign_agents(idea, domain)
            self.req_agents_dedup = self.agg_agents(self.req_agents)
            self.agent_instances = self.load_agents(self.req_agents_dedup)
            return self.req_agents_dedup
        else:
            logger.info(f"Idea '{idea}' is classified under unsupported domain '{domain}'")
            logger.error(f"Domain not supported. Supported domains are {self.SUPPORTED_DOMAINS}")
            logger.error("Exiting...")
            sys.exit(1)

    def run(self):
        ideas = ['create 2048 game']  # Example project ideas, write a cli based snake game, write a design requirement and design document for an AI-powered tool 'create an AI-powered design tool', 'develop a mobile app'
        asyncio.run(self.generate_dynamic_sop(ideas[0]))


if __name__ == "__main__":
    # Assuming the MetaGPT context/config is provided
    company = DynamicSOP(Context(config=config))
    company.run()
