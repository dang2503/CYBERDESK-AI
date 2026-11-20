"""Validated, versionable document structures shared by the editor and exporters."""

import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


KINDS = ("ctf", "incident")
STATUSES = ("Draft", "In Progress", "In Review", "Completed")
IDENTIFIER = r"^[A-Za-z0-9_-]{1,100}$"


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class TemplateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: identifier("section"), pattern=IDENTIFIER)
    title: str = Field(min_length=1, max_length=200)
    level: int = Field(default=2, ge=1, le=6)
    required: bool = True
    instructions: str = Field(default="", max_length=12000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip() or any(x in value for x in ("\n", "\r", "\x00")):
            raise ValueError("Enter a section title on one line.")
        return value.strip()


class DocumentSection(TemplateSection):
    body: str = Field(default="", max_length=2_000_000)


class TemplateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: identifier("template"), pattern=IDENTIFIER)
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["ctf", "incident"]
    description: str = Field(default="", max_length=4000)
    sections: list[TemplateSection] = Field(min_length=1, max_length=100)
    required_fields: list[str] = Field(default_factory=list, max_length=80)
    formatting_rules: list[str] = Field(default_factory=list, max_length=80)
    validation_rules: list[str] = Field(default_factory=list, max_length=80)
    style_defaults: dict[str, str] = Field(default_factory=dict)
    locked: bool = True
    builtin: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return TemplateSection.clean_title(value)

    @model_validator(mode="after")
    def unique_sections(self):
        ids = [s.id for s in self.sections]
        names = [s.title.casefold() for s in self.sections]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise ValueError("Each section needs a unique ID and title.")
        if any(not f.strip() for f in self.required_fields):
            raise ValueError("Required field names cannot be blank.")
        return self


def _template(id_, name, description, headings, required_fields, optional=(), preset="Professional / Technical"):
    kind = id_.split("-")[0]
    is_ctf = kind == "ctf"
    rules = (
        ["Separate Command, Command Output, Observation, Explanation and Result where applicable.",
         "Use fenced code blocks for supplied commands and output. Preserve their text."]
        if is_ctf else
        ["Use Confirmed, Suspected or Unknown for findings and cite existing Evidence IDs.",
         "Keep detection time and start time separate. Preserve source time zones.",
         "Separate observed response actions from recommendations."]
    )
    sections = []
    for title, instructions in headings:
        section_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        sections.append({"id": section_id, "title": title, "required": title not in optional,
                         "instructions": instructions, "level": 2})
    return TemplateSchema(id=id_, name=name, kind=kind, description=description, sections=sections,
                          required_fields=required_fields, formatting_rules=rules, builtin=True,
                          validation_rules=["Check required fields, hierarchy, order, evidence and media references."],
                          style_defaults={"preset": preset, "detail": "Standard", "language": "English",
                                          "perspective": "First Person — I" if is_ctf else "Objective / Impersonal"}).model_dump()


BUILTINS = [
    _template("ctf-professional", "Professional CTF Write-up",
              "Document verified lab observations, findings and lessons in technical detail.", [
        ("Overview", "Identify the challenge, platform, scope and stated objective."),
        ("Reconnaissance", "Summarize observations already recorded in the supplied notes."),
        ("Enumeration", "Describe documented services, versions and evidence without adding steps."),
        ("Vulnerability Analysis", "Describe the documented weakness, uncertainty and defensive implications."),
        ("Exploitation", "Summarize the recorded outcome and impact. Refer to evidence and avoid operational instructions."),
        ("Privilege Escalation", "Record any observed privilege change, its evidence and security implications."),
        ("Lessons Learned", "Connect documented observations with learning and mitigation."),
        ("Conclusion", "Summarize the result and unresolved questions.")],
        ["challenge_name"], ["Reconnaissance", "Enumeration", "Vulnerability Analysis", "Exploitation", "Privilege Escalation"]),
    _template("ctf-educational", "Educational Walkthrough",
              "Explain a lab's context, observations and learning outcomes for new practitioners.", [
        ("Introduction", "Describe the lab and its scope."),
        ("Learning Objectives", "List the learning goals supported by the notes."),
        ("Lab Environment", "Describe only the provided lab environment and constraints."),
        ("Step-by-Step Walkthrough", "Narrate the already recorded observations chronologically, focusing on results and learning."),
        ("Command Explanation", "Explain supplied benign or defensive commands and their recorded output."),
        ("Key Findings", "Separate observations from interpretation."),
        ("Lessons Learned", "Define important terms and connect them to the lab."),
        ("Conclusion", "Summarize what was established.")],
        ["challenge_name"], ["Command Explanation"], preset="Beginner Friendly"),
    _template("ctf-concise", "Concise CTF Write-up",
              "Capture the scope, evidence and result in a short write-up.", [
        ("Challenge Overview", "Identify the challenge and objective."),
        ("Initial Findings", "List the most important observations."),
        ("Solution Steps", "Summarize the documented progression and evidence at a non-operational level."),
        ("Result", "Report only the recorded result."),
        ("Key Takeaways", "List concrete learning points supported by the record.")],
        ["challenge_name"], preset="Concise / Direct"),
    _template("incident-standard", "Standard SOC Incident Report",
              "Create an evidence-linked record of detection, investigation, impact and response.", [
        ("Incident Information", "Present incident ID, title, severity and status as provided."),
        ("Executive Summary", "Briefly explain the observed event, known impact and open questions."),
        ("Incident Description", "Describe the scope and reported circumstances."),
        ("Detection and Evidence", "Identify the detection source and cite evidence."),
        ("Incident Timeline", "Use sourced times with time zones. Keep detection and start distinct."),
        ("Technical Analysis", "Label findings Confirmed, Suspected or Unknown and cite Evidence IDs."),
        ("Indicators of Compromise", "Identify each indicator and its source."),
        ("Impact Assessment", "Distinguish verified impact from possible exposure."),
        ("Response Actions", "Identify completed actions and cite the supplied record."),
        ("Recommendations", "Present proposed future actions."),
        ("Conclusion", "Link conclusions to findings, timeline and evidence."),
        ("Appendix", "Include supporting artifacts or references as needed.")],
        ["incident_id", "severity"], ["Indicators of Compromise", "Appendix"]),
    _template("incident-executive", "Executive Incident Report",
              "Present confirmed business impact, response status and decisions for management.", [
        ("Incident Overview", "Identify the incident and scope."),
        ("Executive Summary", "Describe the incident briefly in plain language."),
        ("Business Impact", "Explain known impact, supported by evidence."),
        ("Response Status", "State which actions are verified, outstanding or unknown."),
        ("Key Risks", "Describe plausible risks and distinguish them from confirmed impact."),
        ("Recommendations", "Present prioritized proposed steps for decision-makers.")],
        ["incident_id", "severity"], preset="Concise / Direct"),
    _template("incident-technical", "Technical Incident Report",
              "Trace technical findings and investigative conclusions to their source evidence.", [
        ("Incident Metadata", "Present the incident identifiers and classification."),
        ("Detection Details", "Identify the detection source and exact detection time if available."),
        ("Evidence Sources", "Describe the source and relevance of each supplied item."),
        ("Event Timeline", "Reconstruct only events with evidence. Retain time zones."),
        ("Technical Investigation", "Distinguish sourced facts, hypotheses and unknowns."),
        ("Affected Systems", "List verified assets and mark unconfirmed scope."),
        ("IOC Analysis", "Cite the origin and context for each indicator."),
        ("Impact Assessment", "Document impact with supporting evidence."),
        ("Response and Containment", "Only report containment actions with confirmation."),
        ("Root Cause Analysis", "State Not Established when evidence cannot establish root cause."),
        ("Recommendations", "List proposed steps and their rationale."),
        ("Appendix", "Reference supporting artifacts and evidence.")],
        ["incident_id", "severity"], ["IOC Analysis", "Appendix"], preset="Detailed / Analytical"),
]
