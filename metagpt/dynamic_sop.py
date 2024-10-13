#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dynamically generates SOP (Standard Operating Procedure) and allocates agents based on the project idea.
"""

from __future__ import annotations
import os
import ast
import asyncio
from metagpt.config2 import config
from metagpt.context import Context
from metagpt.provider.llm_provider_registry import create_llm_instance
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.utils.feedback_collector import llm_feedback_loop, Prompt

role_directory = '/Users/raj/Desktop/uoa/capstone/mgpt/MetaGPT/metagpt/roles'

class RoleInspector:
    def __init__(self, directory, output_file=None):
        self.directory = directory
        self.output_file = output_file

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
    

    def process_file(self, file_path):
        with open(file_path, 'r') as file:
            file_content = file.read()

        tree = ast.parse(file_content)
        role_classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self.is_role_class(node):
                skill = self.get_class_attributes(node)
                agent = {'agent':node.name,'skill': skill}
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
    SUPPORTED_DOMAINS = ['software engineering', 'design', 'consulting']  # Replace with MetaGPT-defined supported domains

    def __init__(self, context):
        self.context = context
        self.llm = create_llm_instance(self.context.config.llm)
        self.inspector = RoleInspector(role_directory)
        self.agents = self.inspector.get_all_role_summary()

    async def classify_idea(self, idea: str | Prompt = None) -> str:
        if not isinstance(idea, Prompt):
            idea = Prompt(f"""
            You are given a task description and a list of supported domains: {self.SUPPORTED_DOMAINS}.
            Classify the task to one of the domains based on key features or keywords.
            
            Task: {idea}

            ### Output format:
            <Domain name> (exact match to one of {self.SUPPORTED_DOMAINS} or 'None')
            """)
        query = idea.adjusted_prompt if idea.adjusted_prompt else idea.prompt
        domain = await self.llm.aask(query)
        llm_feedback_loop(idea, domain)
        if idea.adjusted_prompt:
            domain = await self.classify_idea(idea)
        logger.info(f"Classified idea: {domain.strip()}")
        self.domain = domain.strip()
        return self.domain

    async def generate_dynamic_sop(self, idea: str, domain: str) -> list:
        """
        Dynamically generate SOP roles and responsibilities based on the project idea and domain.
        """
        prompt = f"""
        Given the project idea and domain, generate an SOP (Standard Operating Procedure) dynamically based on the domain.
        Each role should be described with its responsibility and must logically follow based on the task.
        Arrange the roles in logical order.

        Project Idea: {idea}
        Domain: {domain}

        # Output format:
        1. <Role>: <Responsibility>
        2. <Role>: <Responsibility>
        3. <Role>: <Responsibility>
        """
        sop_response = await self.llm.aask(prompt)
        # logger.info(f"Generated SOP roles: {sop_response}")

        return self.parse_roles(sop_response)

    def parse_roles(self, roles_response: str) -> list:
        """
        Parses the output containing roles and their responsibilities.
        It handles both single-line and multi-line (bullet-pointed) responsibilities, combining multi-line responsibilities into a single line.
        
        :param roles_response: The string response containing roles and responsibilities.
        :return: A list of dictionaries where each dictionary contains a role and its combined responsibilities.
        """
        parsed_roles = []
        current_role = None
        current_responsibilities = []

        import re
        # Split the response into lines
        lines = roles_response.strip().split("\n")

        for line in lines:
            # Match lines that start with "<number>. <Role>: <Responsibility>"
            role_match = re.match(r"^\d+\.\s*(.*?):\s*(.*)", line)
            
            # Match lines that are bullet points, e.g., "- Define the project scope"
            bullet_point_match = re.match(r"^\s*-\s*(.*)", line)

            if role_match:
                # If there is a current role and responsibilities, append it to parsed_roles
                if current_role:
                    # Join all multiline responsibilities into a single string separated by commas
                    combined_responsibilities = ", ".join(current_responsibilities)
                    parsed_roles.append({
                        "role": current_role,
                        "responsibilities": combined_responsibilities
                    })

                # Set the new role and its first responsibility (could be empty if it's a multi-line responsibility)
                current_role = role_match.group(1).strip()
                responsibility = role_match.group(2).strip()

                # If there's a single-line responsibility, add it; otherwise, prepare for multi-line responsibilities
                current_responsibilities = [responsibility] if responsibility else []
            
            elif bullet_point_match and current_role:
                # Add bullet points to the current role's responsibilities
                current_responsibilities.append(bullet_point_match.group(1).strip())

        # Add the last role and its responsibilities after the loop ends
        if current_role:
            # Join all multiline responsibilities into a single string separated by commas
            combined_responsibilities = ", ".join(current_responsibilities)
            parsed_roles.append({
                "role": current_role,
                "responsibilities": combined_responsibilities
            })

        return parsed_roles


    async def allocate_agents(self, roles: list) -> list:
        """
        Allocates agents to dynamically generated roles based on their skills.
        If no matching agent is found, assigns '<TODO>' to that role.
        """
        prompt = f"""
        Your task is to assign agents to the following roles based on their skills. Each role has a responsibility.
        For each role, if an agent matches the skill required for the role, return their name and their skill.
        If no agent matches the role's skill, return '<TODO>' as the agent.

        Roles: {roles}
        Agents: {self.agents}
        
        # Output format:
        1. <Role>: <Responsibility>
           <Agent>: <Skill>
        2. <Role>: <Responsibility>
           <Agent>: <Skill>
        ...
        """
        
        agents_response = await self.llm.aask(prompt)
        # logger.info(f"Agents allocated: {agents_response}")

        return self.parse_agents_response(agents_response)

    def parse_agents_response(self, assignment_response: str) -> list:
        """
        Parses the output of agent assignment, returning a structured list of roles, responsibilities, agents, and their skills.
        It also handles cases where no agent is assigned, represented by <TODO>.

        :param assignment_response: The string response from the LLM for agent assignment.
        :return: A list of dictionaries, where each dictionary contains role, responsibility, agent, and skill.
        """
        # Define a list to hold the parsed data
        parsed_data = []
        
        import re
        # Split the response into individual sections
        sections = assignment_response.strip().split("\n")
        
        # Temporary variables to hold role, responsibility, agent, and skill
        role, responsibility, agent, skill = None, None, None, None
        
        for line in sections:
            # Match the role and responsibility line (e.g., "1. Developer: Responsible for writing...")
            role_responsibility_match = re.match(r"^\d+\.\s*(.*?):\s*(.*)", line)
            # Match the agent and skill line (e.g., "Engineer: write elegant, readable...")
            agent_skill_match = re.match(r"^(.*?):\s*(.*)", line)

            if role_responsibility_match:
                # If we already have a role and agent from the previous iteration, store it in parsed_data
                if role is not None:
                    parsed_data.append({
                        "role": role,
                        "responsibility": responsibility,
                        "agent": agent ,
                        "skill": skill
                    })
                
                # Extract the new role and responsibility
                role = role_responsibility_match.group(1).strip()
                responsibility = role_responsibility_match.group(2).strip()

                # Reset agent and skill for the new role
                agent, skill = None, None

            elif agent_skill_match:
                # Extract the agent and skill
                agent = agent_skill_match.group(1).strip()
                skill = agent_skill_match.group(2).strip()

            
        # Add the last entry after the loop ends
        if role is not None:
            parsed_data.append({
                "role": role,
                "responsibility": responsibility,
                "agent": agent ,
                "skill": skill
            })
        
        return parsed_data



    async def run_project(self, idea: str):
        domain = await self.classify_idea(idea)
        if domain in self.SUPPORTED_DOMAINS:
            # Generate the SOP dynamically based on the idea and domain
            roles = await self.generate_dynamic_sop(idea, domain)
            # print("*"*40)
            # print("SOP")
            # print(roles)
            # detailed_sop = await self.generate_dynamic_sop_from_roles(roles, domain)
            agent_allocations = await self.allocate_agents(roles)
            print("*"*40)
            print("agent allocation")
            print(agent_allocations)

            # logger.info(f"Project setup: {agent_allocations}")
            # Output the parsed data
            for entry in agent_allocations:
                print("-" * 40)
                print(f"Role: {entry['role']}")
                print(f"Responsibility: {entry['responsibility']}")
                print(f"Agent: {entry['agent']}")
                print(f"Skill: {entry['skill']}")
                print("-" * 40)
        else:
            logger.error(f"Domain not supported. Supported domains are {self.SUPPORTED_DOMAINS}")

    def run(self):
        ideas = ['write a CLI based snake game']  # Example project ideas, , 'create an AI-powered design tool', 'develop a mobile app'
        for idea in ideas:
            asyncio.run(self.run_project(idea))


if __name__ == "__main__":
    # Assuming the MetaGPT context/config is provided
    company = DynamicSOP(Context(config=config))
    from metagpt.utils.feedback_collector import FEEDBACK_REGISTRY
    FEEDBACK_REGISTRY.collect_feedback = True
    company.run()
