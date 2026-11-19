## Summary

<!-- What this changes and why, in 2 to 4 sentences. Lead with the main point. Follow the Writing style section of AGENTS.md. -->

## Testing

<!-- What you ran and what you saw. Say what you measured and what you didn't test. -->

- [ ] `claude plugin validate --strict .`
- [ ] `claude plugin validate --strict plugins/cortex-xcor-rum`
- [ ] `claude plugin validate --profile directory plugins/cortex-xcor-rum`
- [ ] `python3 scripts/check-plugin.py`

## Checklist

- [ ] If files under `plugins/cortex-xcor-rum/` changed: `version` in `plugin.json` is bumped (once a version has shipped) and `CHANGELOG.md` has an entry
- [ ] A new skill is listed in `README.md` and `plugins/cortex-xcor-rum/README.md`
- [ ] No credentials, customer data, internal links or promises
- [ ] Prose calls the product XCOR RUM
