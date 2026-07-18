"""Unit tests for validate_deliver_receipt — the core deliver gate.

Strategy: start from a known-good receipt, perturb one thing at a time, and
assert the specific error surfaces. Substring assertions keep the tests robust
to unrelated derived errors.
"""


def errs(guard, receipt, contract, facts=None):
    return guard.validate_deliver_receipt(receipt, contract, facts or {})


def test_golden_receipt_has_no_errors(guard, good_receipt, light_contract):
    assert errs(guard, good_receipt, light_contract) == []


def test_missing_required_field_is_reported(guard, good_receipt, light_contract):
    bad = dict(good_receipt)
    bad.pop("verification_command")
    result = errs(guard, bad, light_contract)
    assert any("missing required fields" in e and "verification_command" in e for e in result)


def test_changed_files_must_be_non_empty_list(guard, good_receipt, light_contract):
    bad = dict(good_receipt)
    bad["changed_files"] = []
    result = errs(guard, bad, light_contract)
    assert any("changed_files must be a non-empty list" in e for e in result)


def test_affected_layers_must_be_non_empty_list(guard, good_receipt, light_contract):
    bad = dict(good_receipt)
    bad["affected_layers"] = []
    result = errs(guard, bad, light_contract)
    assert any("affected_layers must be a non-empty list" in e for e in result)


def test_unclean_result_requires_limitation(guard, good_receipt, light_contract):
    bad = dict(good_receipt)
    bad["result"] = "tests failed"
    result = errs(guard, bad, light_contract)
    assert any("limitation is required" in e for e in result)

    # Adding a limitation clears the requirement.
    bad["limitation"] = "flaky network dependency, retried manually"
    assert errs(guard, bad, light_contract) == []


def test_receipt_must_cover_changed_files_from_diff_facts(guard, good_receipt, light_contract):
    facts = {"changed_files": {"src/untracked.py": {"layer": "Tools"}}}
    result = errs(guard, good_receipt, light_contract, facts)
    assert any("receipt missing changed_files from diff facts" in e for e in result)


def test_receipt_must_cover_affected_layers_from_diff_facts(guard, good_receipt, light_contract):
    # Receipt lists the file but not its layer.
    receipt = dict(good_receipt)
    receipt["changed_files"] = ["src/untracked.py"]
    receipt["affected_layers"] = ["Identity"]
    facts = {"changed_files": {"src/untracked.py": {"layer": "Tools"}}}
    result = errs(guard, receipt, light_contract, facts)
    assert any("receipt missing affected_layers from diff facts" in e for e in result)


def test_strict_preset_rejects_unclean_verification(guard, good_receipt):
    receipt = dict(good_receipt)
    receipt["operational_preset"] = "strict"
    receipt["result"] = "skipped"
    receipt["limitation"] = "sandbox blocked the command"
    result = errs(guard, receipt, {"operational_preset": "strict"})
    assert any("strict preset requires clean verification" in e for e in result)


def test_invalid_preset_is_reported(guard, good_receipt):
    receipt = dict(good_receipt)
    receipt["operational_preset"] = "turbo"
    result = errs(guard, receipt, {"operational_preset": "turbo"})
    assert any("operational_preset must be" in e for e in result)


def test_out_of_scope_path_is_rejected(guard, good_receipt):
    contract = {
        "operational_preset": "light",
        "allowed_paths": ["pilothOS/**"],
        "out_of_scope_paths": ["pilothOS/scripts/**"],
    }
    facts = {"changed_files": {"pilothOS/scripts/pilothos_guard.py": {"layer": "Tools"}}}
    result = errs(guard, good_receipt, contract, facts)
    assert any("out_of_scope" in e for e in result)


def test_non_dict_receipt_rejected(guard, light_contract):
    assert errs(guard, "not-a-dict", light_contract) == ["receipt must be a JSON object"]
