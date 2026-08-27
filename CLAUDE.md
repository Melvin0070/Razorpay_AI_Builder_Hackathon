# LeakProof

Marketplace settlement leakage auditor and claim-recovery agent.
Razorpay AI Buildathon, Track 04 (AI Finance Controller).

Architecture principle: **deterministic money, probabilistic language.** The LLM
parses, explains, classifies, and drafts. It never computes a rupee amount and
never files anything. Every number traces to a source row. Every action lands in
an append-only audit trail. Every claim is human-approved.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec
