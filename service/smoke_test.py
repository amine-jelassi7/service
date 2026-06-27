#!/usr/bin/env python3
"""smoke_test.py — run this on the VM to verify the service works correctly
before using a grading submission.

Usage (with service already running):
    python3 smoke_test.py

Or test predict_batch directly (no HTTP):
    python3 smoke_test.py --direct
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"

EXAMPLE_REQUEST = {
    "instances": [
        {
            "ID": 4,
            "dri_score": "High",
            "psych_disturb": "No",
            "cyto_score": None,
            "diabetes": "No",
            "hla_match_c_high": 2,
            "hla_high_res_8": 8,
            "tbi_status": "No TBI",
            "arrhythmia": "No",
            "hla_low_res_6": 6,
            "graft_type": "Peripheral blood",
            "vent_hist": "No",
            "renal_issue": "No",
            "pulm_severe": "No",
            "prim_disease_hct": "MPN",
            "hla_high_res_6": 6,
            "cmv_status": "+/+",
            "hla_high_res_10": 10,
            "hla_match_dqb1_high": 2,
            "tce_imm_match": None,
            "hla_nmdp_6": 5,
            "hla_match_c_low": 2,
            "rituximab": "No",
            "hla_match_drb1_low": 2,
            "hla_match_dqb1_low": 2,
            "prod_type": "PB",
            "cyto_score_detail": None,
            "conditioning_intensity": "MAC",
            "ethnicity": "Hispanic or Latino",
            "year_hct": 2018,
            "obesity": "No",
            "mrd_hct": None,
            "in_vivo_tcd": "Yes",
            "tce_match": None,
            "hla_match_a_high": 2,
            "hepatic_severe": "No",
            "donor_age": 56.81,
            "prior_tumor": "No",
            "hla_match_b_low": 2,
            "peptic_ulcer": "No",
            "age_at_hct": 29.74,
            "hla_match_a_low": 2,
            "gvhd_proph": "TDEPLETION +- other",
            "rheum_issue": "No",
            "sex_match": "M-F",
            "hla_match_b_high": 2,
            "race_group": "American Indian or Alaska Native",
            "comorbidity_score": 1,
            "karnofsky_score": 90,
            "hepatic_mild": "No",
            "tce_div_match": "Permissive mismatched",
            "donor_related": "Related",
            "melphalan_dose": "MEL",
            "hla_low_res_8": 8,
            "cardiac": "No",
            "hla_match_drb1_high": 2,
            "pulm_moderate": "No",
            "hla_low_res_10": 10,
        },
        {
            "ID": 1,
            "dri_score": "Intermediate",
            "psych_disturb": "No",
            "cyto_score": "Intermediate",
            "diabetes": "No",
            "hla_match_c_high": 2,
            "hla_high_res_8": 8,
            "tbi_status": "TBI +- Other, >cGy",
            "arrhythmia": "No",
            "hla_low_res_6": 6,
            "graft_type": "Peripheral blood",
            "vent_hist": "No",
            "renal_issue": "No",
            "pulm_severe": "No",
            "prim_disease_hct": "AML",
            "hla_high_res_6": 6,
            "cmv_status": "+/+",
            "hla_high_res_10": 10,
            "hla_match_dqb1_high": 2,
            "tce_imm_match": "P/P",
            "hla_nmdp_6": 6,
            "hla_match_c_low": 2,
            "rituximab": "No",
            "hla_match_drb1_low": 2,
            "hla_match_dqb1_low": 2,
            "prod_type": "PB",
            "cyto_score_detail": "Intermediate",
            "conditioning_intensity": "MAC",
            "ethnicity": "Not Hispanic or Latino",
            "year_hct": 2008,
            "obesity": "No",
            "mrd_hct": "Positive",
            "in_vivo_tcd": "No",
            "tce_match": "Permissive",
            "hla_match_a_high": 2,
            "hepatic_severe": "No",
            "donor_age": 72.29,
            "prior_tumor": "No",
            "hla_match_b_low": 2,
            "peptic_ulcer": "No",
            "age_at_hct": 43.705,
            "hla_match_a_low": 2,
            "gvhd_proph": "Other GVHD Prophylaxis",
            "rheum_issue": "No",
            "sex_match": "F-F",
            "hla_match_b_high": 2,
            "race_group": "Asian",
            "comorbidity_score": 3,
            "karnofsky_score": 90,
            "hepatic_mild": "No",
            "tce_div_match": "Permissive mismatched",
            "donor_related": "Related",
            "melphalan_dose": "N/A, Mel not given",
            "hla_low_res_8": 8,
            "cardiac": "No",
            "hla_match_drb1_high": 2,
            "pulm_moderate": "Yes",
            "hla_low_res_10": 10,
        },
    ]
}


def test_health():
    print("── /health ─────────────────────────────")
    req = urllib.request.Request(f"{BASE_URL}/health")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            assert body == {"status": "ok"}, f"unexpected: {body}"
            print(f"  ✓ {body}")
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)


def test_predict():
    print("── /predict ────────────────────────────")
    payload = json.dumps(EXAMPLE_REQUEST).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/predict",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            elapsed = time.perf_counter() - t0
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    preds = {p["ID"]: p["prediction"] for p in body["predictions"]}
    print(f"  Latency: {elapsed*1000:.1f}ms")
    print(f"  Predictions: {preds}")

    # Basic sanity checks
    assert set(preds.keys()) == {4, 1}, f"missing IDs: {preds.keys()}"
    for id_, score in preds.items():
        assert 0.0 <= score <= 1.0, f"ID {id_}: score {score} out of [0,1]"
    print("  ✓ All IDs present, scores in [0,1]")


def test_null_handling():
    print("── /predict (null-heavy) ───────────────")
    # Send a record with lots of nulls
    instance = {k: None for k in EXAMPLE_REQUEST["instances"][0]}
    instance["ID"] = 99
    payload = json.dumps({"instances": [instance]}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/predict",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            preds = body["predictions"]
            assert len(preds) == 1
            assert preds[0]["ID"] == 99
            print(f"  ✓ null-heavy record → {preds[0]['prediction']:.4f}")
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)


def test_unknown_category():
    print("── /predict (unseen category) ──────────")
    instance = dict(EXAMPLE_REQUEST["instances"][0])
    instance["ID"] = 98
    instance["dri_score"] = "UNSEEN_CATEGORY_XYZ"
    payload = json.dumps({"instances": [instance]}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/predict",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            preds = body["predictions"]
            assert len(preds) == 1
            print(f"  ✓ unseen category → {preds[0]['prediction']:.4f}")
    except Exception as e:
        print(f"  ✗ {e}")
        sys.exit(1)


def test_direct():
    """Test predict_batch() directly without HTTP (useful for debugging preload)."""
    print("── direct predict_batch() test ─────────")
    import pandas as pd
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent / "worker"))
    from preload import predict_batch

    df = pd.DataFrame(EXAMPLE_REQUEST["instances"])
    t0 = time.perf_counter()
    scores = predict_batch(df)
    elapsed = time.perf_counter() - t0
    print(f"  Latency: {elapsed*1000:.1f}ms")
    for i, (row, score) in enumerate(zip(EXAMPLE_REQUEST["instances"], scores)):
        print(f"  ID={row['ID']} → {score:.6f}")
    print("  ✓ predict_batch OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true",
                        help="Test predict_batch() directly (no HTTP server needed)")
    parser.add_argument("--url", default=BASE_URL,
                        help=f"Base URL (default: {BASE_URL})")
    args = parser.parse_args()

    BASE_URL = args.url

    if args.direct:
        test_direct()
    else:
        test_health()
        test_predict()
        test_null_handling()
        test_unknown_category()
        print("\n✓ All smoke tests passed!")
