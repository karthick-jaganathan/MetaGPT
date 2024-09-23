#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
"""

from __future__ import annotations
from typing import List, Type, AnyStr
from enum import Enum
import asyncio

from metagpt.config2 import config
from metagpt.context import Context
from metagpt.provider.llm_provider_registry import create_llm_instance
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.roles import (
        Architect,
        Engineer,
        ProductManager,
        ProjectManager,
        QaEngineer,
    )
from metagpt.team import Team


class Domain(Enum):
    SOFTWARE_DEVELOPMENT = "software development"
    NON_SOFTWARE_DEVELOPMENT = "non-software development"


class DomainClassifier:

    def __init__(self, context: Context, model: str = None) -> None:
        self.context = context
        self.llm = create_llm_instance(config.llm)
        self.model = model

    async def _llm_classifier(self, idea: str) -> Domain:
        prompt = f"""
        Role: You are a project manager in a software company. You have been given an idea for a software development project.

        You need to classify the given idea is a software development task or non-software development task.

        # Attention: If the idea is a software development project, please answer 'Yes, the domain of the idea is a software development project.'

        Idea: {idea}

        # Output format:
        Yes, the domain of the idea is a software development project.
        """
        domain = await self.llm.aask(prompt)
        if domain.lower().strip().startswith("yes"):
            return Domain.SOFTWARE_DEVELOPMENT
        else:
            return Domain.NON_SOFTWARE_DEVELOPMENT

    async def _classifier(self, idea: str) -> Domain:
        import torch
        from transformers import pipeline
        device = 0 if torch.cuda.is_available() else -1
        logger.info("zero-shot-classification pipeline for domain classification with model: {self.model}")
        classifier = pipeline("zero-shot-classification", model=self.model, device=device)
        candidate_labels = ["software development", "non-software development"]
        prompt = f"classify the idea is a software developmet task or not: {idea}"
        result = classifier(prompt, candidate_labels)
        logger.info(f"classification scores: {result}")
        labels, scores = result["labels"], result["scores"]
        classified_domain = labels[scores.index(max(scores))]
        logger.info(f"Classified idea as a {classified_domain!r} task")
        return Domain(classified_domain)

    async def classify_domain(self, idea: str) -> Domain:
        if self.model:
            return await self._classifier(idea)
        return await self._llm_classifier(idea)


class Company:
    SUPPORTED_DOMAINS = [Domain.SOFTWARE_DEVELOPMENT]

    def __init__(self, context: Context, domain_classifier: DomainClassifier) -> None:
        self.context = context
        self.domain_classifier = domain_classifier
        self.llm = create_llm_instance(config.llm)
        self.idea = None
        self.investment = 3

    async def identify_teams(self) -> None:
        prompt = """
        Role: You are a project manager in a software company. You have been given an idea for a software development project.

        You need to identify the applicable team members roles to work on the project.

        # Attention 1: Pick the suitable ones, no need to list all the roles.
        # Attention 2: You can add more roles if you think they are necessary.

        Idea: {idea}

        # Output format:
        Team members required:
        <TEAMS>
        1. <Role>: <responsibility>
        </TEAMS>
        For example:
            Team members required:
            1. Product Manager: Define the product requirements and prioritize the product features.
            2. Project Manager: Break down tasks according to PRD/technical design, generate a task list, and analyze task dependencies to start with the prerequisite modules.
            3. Architect: Design a concise, usable, complete software system.
            4. Engineer: Implement the software system.
            5. QA Engineer: Test the software system.
            etc.
        """.format(idea=self.idea)

        def parse_response(teams: str) -> list:
            team_list = []
            import re
            for team in teams.split("\n"):
                res = re.match(r"\d+\.\s(.+):\s(.+)", team)
                team = res.groups() if res else None
                if team:
                    team_list.append(team[0])
            return team_list

        teams = await self.llm.aask(prompt)
        domain_expert_roles = parse_response(teams)
        logger.info(f"Identified teams: {domain_expert_roles}")

    def run_project(self, idea: AnyStr) -> None:
        self.idea = idea
        logger.info(f"Running project: {self.idea}")
        if self.idea is None:
            logger.error("Please set the idea before running the project.")
            return
        domain = asyncio.run(self.domain_classifier.classify_domain(self.idea))
        if domain not in self.SUPPORTED_DOMAINS:
            logger.error(f"Identified domain is not supported. Supported domains are {self.SUPPORTED_DOMAINS}")
            raise Exception("Unsupported domain")

    async def hire(self) -> Team:
        teams = await self.identify_teams()
        # TODO: map team members to roles
        roles = []
        team = Team(context=self.context)
        team.hire(roles)
        return team

    async def run(self, n_round) -> None:
        team = await self.hire()
        team.invest(self.investment)
        await team.run(n_round=n_round)

    def invest(self, investment: float) -> None:
        self.investment = investment


if __name__ == "__main__":
    company = Company(Context(config=config), DomainClassifier(Context(config=config)))
    idea = "Develop a web application for managing tasks"
    company.run_project(idea)
    asyncio.run(company.run(n_round=5))
