import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_ENV"] = "test"
os.environ["NEO4J_ENABLED"] = "false"
os.environ["APP_SECRET"] = "test-secret-at-least-thirty-two-characters"
os.environ["ADMIN_PASSWORD"] = "Test-Only-Admin-Password-123!"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "machine-service-test-uploads")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.embeddings import cosine_similarity  # noqa: E402
from app.services.parser import _chunk_text  # noqa: E402


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Test-Only-Admin-Password-123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_auth_catalog_and_health():
    with TestClient(app) as client:
        headers = login(client)
        products = client.get("/api/v1/products", headers=headers)
        assert products.status_code == 200
        codes = {item["code"] for item in products.json()}
        assert {"VMC1000II", "VMC1200II", "V8H"}.issubset(codes)
        assert client.get("/api/v1/health").json()["database"] is True
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").json() == {
            "status": "ready",
            "database": True,
        }
        coverage = client.get("/api/v1/dashboard", headers=headers).json()["graph_coverage"]
        assert coverage == {
            "available": False,
            "subsystems": 0,
            "models": 0,
            "alarms": 0,
            "parts": 0,
            "cases": 0,
        }


def test_request_id_is_returned_and_written_to_audit():
    request_id = "test-request-20260918"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"X-Request-ID": request_id},
            json={"username": "admin", "password": "Test-Only-Admin-Password-123!"},
        )
        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == request_id

        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        logs = client.get("/api/v1/admin/audit", headers=headers).json()
        login_log = next(
            item
            for item in logs
            if item["action"] == "auth.login"
            and item["detail"].get("request_id") == request_id
        )
        assert login_log["detail"]["request_id"] == request_id

        generated = client.get(
            "/api/v1/health/live", headers={"X-Request-ID": "invalid"}
        )
        assert generated.status_code == 200
        assert generated.headers["X-Request-ID"] != "invalid"
        assert len(generated.headers["X-Request-ID"]) == 32


def test_question_has_boundary_and_citations():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 应该先检查什么？",
                "model_code": "VMC1000II",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["requires_engineer_confirmation"] is True
        assert data["citations"]
        assert "演示流程数据" in data["answer"]
        assert any(item["data_classification"] == "demo_process_data" for item in data["citations"])


def test_graph_path_enriches_fault_answer_with_related_part(monkeypatch):
    monkeypatch.setattr(
        "app.services.qa.graph_service.fault_context",
        lambda model_code, alarm_code: {
            "model_code": model_code,
            "alarm_code": alarm_code,
            "subsystems": [
                {
                    "code": "ATC",
                    "name": "机械手式刀库与换刀系统",
                    "source_title": "海天精工立式加工中心公开产品目录",
                    "source_url": "https://haitianprecision.com/wp-content/uploads/2020/06/VMC_GU_2020.5.pdf",
                    "source_section": "VMC II 刀库：24 刀机械手刀库",
                    "data_classification": "official_public",
                    "alarm_source_title": "演示故障关联：待企业受控资料复核",
                    "alarm_source_url": None,
                    "alarm_source_section": "换刀气路压力关联样例",
                    "alarm_data_classification": "demo_process_data",
                }
            ],
            "parts": [
                {
                    "part_no": "DEMO-AIR-FILTER-01",
                    "name": "演示气路过滤元件",
                    "source_title": "演示故障关联：待企业受控资料复核",
                    "source_url": None,
                    "source_section": "换刀气路压力关联样例",
                    "data_classification": "demo_process_data",
                }
            ],
            "cases": [
                {
                    "case_no": "DEMO-CASE-2026-001",
                    "title": "演示案例：换刀过程中气压条件不满足",
                    "data_classification": "demo_process_data",
                }
            ],
        },
    )
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 应该先检查什么？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "知识图谱关联" in data["answer"]
        assert any(
            item["path"] == ["VMC1000II", "机械手式刀库与换刀系统"]
            for item in data["relation_paths"]
        )
        assert any(item["data_classification"] == "official_public" for item in data["relation_paths"])
        assert any(item["data_classification"] == "demo_process_data" for item in data["relation_paths"])
        assert any(item["source_type"] == "part" for item in data["citations"])
        assert "已使用已审核知识图谱" in data["graph_notice"]


def test_uncovered_fault_reports_graph_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.services.qa.graph_service.fault_context",
        lambda model_code, alarm_code: {
            "model_code": model_code,
            "alarm_code": alarm_code,
            "subsystems": [],
            "parts": [],
            "cases": [
                {
                    "case_no": "DEMO-CASE-2026-002",
                    "title": "演示案例：连续加工后主轴温度趋势上升",
                    "data_classification": "demo_process_data",
                }
            ],
        },
    )
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "V8H 出现 SP-2001 主轴温升异常怎么排查？",
                "model_code": "V8H",
                "serial_number": "TEST-SN-002",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["relation_paths"] == []
        assert "暂无已审核的图谱关联" in data["graph_notice"]
        assert "结构化数据与文档检索" in data["graph_notice"]


def test_unknown_question_refuses_to_guess():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "完全不存在的 ZX-9999 神秘故障"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] <= 0.2
        assert "没有找到足够可靠的依据" in data["answer"]


def test_known_model_with_unknown_fault_does_not_fall_back_to_product_specs():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "VMC1000II 出现 ZZZ-9999 未知故障", "model_code": "VMC1000II"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] <= 0.2
        assert "没有找到足够可靠的依据" in data["answer"]
        assert "公开参数" not in data["answer"]


def test_invalid_supplied_model_is_rejected_early():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "出现报警怎么办", "model_code": "NOT-A-MODEL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] == 0.1
        assert "没有找到机型" in data["answer"]


def test_part_question_returns_part_evidence():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 主轴冷却过滤元件的备件怎么核对？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-001",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert any(item["source_type"] == "part" for item in data["citations"])
        assert not any(item["source_type"] == "alarm" for item in data["citations"])
        assert "禁止按演示编号采购" in data["answer"]


def test_multi_turn_context_inherits_fault_and_advances_checks():
    with TestClient(app) as client:
        headers = login(client)
        first = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001，自动换刀中止，先检查什么？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-CONTEXT-001",
            },
        )
        assert first.status_code == 200
        first_data = first.json()
        assert first_data["context"]["alarm_code"] == "ATC-1001"

        follow_up = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "第二步已完成，气源压力显示正常，但还是不行，下一步呢？",
                "conversation_id": first_data["conversation_id"],
            },
        )
        assert follow_up.status_code == 200
        data = follow_up.json()
        assert data["context"]["model_code"] == "VMC1000II"
        assert data["context"]["serial_number"] == "TEST-SN-CONTEXT-001"
        assert data["context"]["alarm_code"] == "ATC-1001"
        assert data["context"]["status"] == "investigating"
        assert data["context"]["history_turns_used"] == 1
        assert data["context"]["completed_checks"] == [
            "由授权人员核对机床铭牌、控制系统版本和气源压力显示"
        ]
        assert "报警代码" in data["context_notice"]
        assert "下一步建议检查" in data["answer"]
        assert "已排除本次会话中确认完成的步骤" in data["answer"]
        assert "机床序列号" not in data["missing_information"]
        assert any(item["source_type"] == "alarm" for item in data["citations"])


def test_new_alarm_switches_context_and_clears_old_progress():
    with TestClient(app) as client:
        headers = login(client)
        first = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 怎么排查？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-CONTEXT-002",
            },
        ).json()
        client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "第一步完成了，还是不行", "conversation_id": first["conversation_id"]},
        )

        switched = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "现在出现 SP-2001 主轴温升异常，应该怎么排查？",
                "conversation_id": first["conversation_id"],
            },
        )
        assert switched.status_code == 200
        context = switched.json()["context"]
        assert context["model_code"] == "VMC1000II"
        assert context["alarm_code"] == "SP-2001"
        assert context["completed_checks"] == []
        assert context["latest_feedback"] is None
        assert any("SP-2001" in item["title"] for item in switched.json()["citations"]), switched.json()


def test_context_reset_does_not_rehydrate_old_fault_history():
    with TestClient(app) as client:
        headers = login(client)
        first = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 怎么排查？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-CONTEXT-003",
            },
        ).json()
        conversation_id = first["conversation_id"]

        reset = client.post(
            f"/api/v1/qa/conversations/{conversation_id}/context/reset",
            headers=headers,
        )
        assert reset.status_code == 200
        assert reset.json()["model_code"] is None
        assert reset.json()["alarm_code"] is None

        follow_up = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "下一步呢？", "conversation_id": conversation_id},
        )
        assert follow_up.status_code == 200
        data = follow_up.json()
        assert data["context"]["model_code"] is None
        assert data["context"]["alarm_code"] is None
        assert data["context"]["history_turns_used"] == 0
        assert data["confidence"] <= 0.2


def test_resolved_follow_up_closes_fault_instead_of_repeating_checks():
    with TestClient(app) as client:
        headers = login(client)
        first = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 怎么排查？",
                "model_code": "VMC1000II",
                "serial_number": "TEST-SN-CONTEXT-004",
            },
        ).json()
        closed = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={"question": "问题已经解决，设备恢复正常", "conversation_id": first["conversation_id"]},
        )
        assert closed.status_code == 200
        data = closed.json()
        assert data["context"]["status"] == "resolved"
        assert "已记录" in data["answer"]
        assert "本次故障恢复" in data["answer"]
        assert "建议检查顺序" not in data["answer"]


def test_model_switch_isolates_old_serial_alarm_and_history():
    with TestClient(app) as client:
        headers = login(client)
        first = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "VMC1000II 出现 ATC-1001 怎么排查？",
                "model_code": "VMC1000II",
                "serial_number": "OLD-MACHINE-SERIAL",
            },
        ).json()
        switched = client.post(
            "/api/v1/qa/ask",
            headers=headers,
            json={
                "question": "换成 V8H，开始排查另一台设备",
                "conversation_id": first["conversation_id"],
            },
        )
        assert switched.status_code == 200
        context = switched.json()["context"]
        assert context["model_code"] == "V8H"
        assert context["serial_number"] is None
        assert context["alarm_code"] is None
        assert context["completed_checks"] == []
        assert context["history_turns_used"] == 0


def test_unauthenticated_access_is_rejected():
    with TestClient(app) as client:
        assert client.get("/api/v1/products").status_code == 401


def test_document_parse_extract_and_publish_workflow():
    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/documents",
            headers=headers,
            data={
                "title": "测试报警与备件手册",
                "doc_type": "alarm_manual",
                "version": "T-1.0",
                "model_codes": "VMC1000II",
            },
            files={
                "file": (
                    "workflow-test.txt",
                    "# 报警说明\n\n报警 ATC-5555，请核对受控流程。\n\n备件号：DEMO-TEST-7788。".encode(),
                    "text/plain",
                )
            },
        )
        assert response.status_code == 201
        document = response.json()
        assert document["parse_status"] == "complete"
        assert "待审核候选知识" in document["parse_message"]

        pending = client.get("/api/v1/knowledge", headers=headers, params={"status": "pending"})
        assert pending.status_code == 200
        assert any("ATC-5555" in item["title"] for item in pending.json())
        candidate = next(item for item in pending.json() if "ATC-5555" in item["title"])

        blocked = client.patch(
            f"/api/v1/knowledge/{candidate['id']}/review",
            headers=headers,
            json={"status": "published"},
        )
        assert blocked.status_code == 409

        published = client.patch(
            f"/api/v1/documents/{document['id']}/review",
            headers=headers,
            json={"status": "published", "note": "测试发布"},
        )
        assert published.status_code == 200
        assert published.json()["review_status"] == "published"

        knowledge_published = client.patch(
            f"/api/v1/knowledge/{candidate['id']}/review",
            headers=headers,
            json={"status": "published"},
        )
        assert knowledge_published.status_code == 200

        deprecated = client.patch(
            f"/api/v1/documents/{document['id']}/review",
            headers=headers,
            json={"status": "deprecated", "note": "测试状态联动"},
        )
        assert deprecated.status_code == 200
        knowledge_after = client.get("/api/v1/knowledge", headers=headers).json()
        linked = next(item for item in knowledge_after if item["id"] == candidate["id"])
        assert linked["review_status"] == "deprecated"


def test_empty_file_and_unknown_model_upload_are_rejected():
    with TestClient(app) as client:
        headers = login(client)
        empty = client.post(
            "/api/v1/documents",
            headers=headers,
            data={"title": "空文件测试", "version": "E-1"},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert empty.status_code == 400

        unknown_model = client.post(
            "/api/v1/documents",
            headers=headers,
            data={"title": "未知机型测试", "version": "E-2", "model_codes": "UNKNOWN-1"},
            files={"file": ("unknown.txt", "测试内容".encode(), "text/plain")},
        )
        assert unknown_model.status_code == 422


def test_long_paragraph_chunking_preserves_limits_and_headings():
    chunks = _chunk_text("# 第一节\n\n" + "主轴温升异常。" * 400, max_chars=300, overlap=40)
    assert len(chunks) > 2
    assert all(len(chunk.content) <= 300 for chunk in chunks)
    assert all(chunk.heading == "第一节" for chunk in chunks)


def test_cosine_similarity_accepts_pgvector_array_like_values():
    class VectorLike(list):
        def __bool__(self):
            raise ValueError("array truth value is ambiguous")

    assert cosine_similarity(VectorLike([0.5, -0.5]), [0.5, 0.5]) == 0.0
    assert cosine_similarity(VectorLike(), [1.0]) == 0.0


def test_password_change_requires_current_password_and_is_reversible():
    with TestClient(app) as client:
        headers = login(client)
        denied = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "WrongPassword!", "new_password": "A-New-Password-123!"},
        )
        assert denied.status_code == 400
        changed = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "Test-Only-Admin-Password-123!",
                "new_password": "A-New-Password-123!",
            },
        )
        assert changed.status_code == 200
        assert client.get("/api/v1/products", headers=headers).status_code == 401
        relogin = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "A-New-Password-123!"},
        )
        assert relogin.status_code == 200
        new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
        reverted = client.post(
            "/api/v1/auth/change-password",
            headers=new_headers,
            json={
                "current_password": "A-New-Password-123!",
                "new_password": "Test-Only-Admin-Password-123!",
            },
        )
        assert reverted.status_code == 200


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setattr("app.main._database_ready", lambda: False)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "database": False}


def test_login_lockout_is_persistent_and_admin_can_unlock():
    with TestClient(app) as client:
        admin_headers = login(client)
        created = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": "lockout-user",
                "display_name": "锁定测试用户",
                "password": "Lockout-User-Password-123!",
                "role": "engineer",
            },
        )
        assert created.status_code == 201
        user_id = created.json()["id"]

        for _ in range(4):
            denied = client.post(
                "/api/v1/auth/login",
                json={"username": "lockout-user", "password": "Wrong-Password-123!"},
            )
            assert denied.status_code == 401
        locked = client.post(
            "/api/v1/auth/login",
            json={"username": "lockout-user", "password": "Wrong-Password-123!"},
        )
        assert locked.status_code == 429
        assert int(locked.headers["Retry-After"]) > 0

        correct_but_locked = client.post(
            "/api/v1/auth/login",
            json={"username": "lockout-user", "password": "Lockout-User-Password-123!"},
        )
        assert correct_but_locked.status_code == 429

        unlocked = client.post(
            f"/api/v1/admin/users/{user_id}/unlock",
            headers=admin_headers,
        )
        assert unlocked.status_code == 200
        assert unlocked.json()["locked_until"] is None

        relogin = client.post(
            "/api/v1/auth/login",
            json={"username": "lockout-user", "password": "Lockout-User-Password-123!"},
        )
        assert relogin.status_code == 200
        assert relogin.json()["user"]["last_login_at"] is not None


def test_admin_can_disable_user_but_not_current_account():
    with TestClient(app) as client:
        admin_headers = login(client)
        created = client.post(
            "/api/v1/admin/users",
            headers=admin_headers,
            json={
                "username": "lifecycle-user",
                "display_name": "账号生命周期测试",
                "password": "Lifecycle-Password-123!",
                "role": "viewer",
            },
        )
        assert created.status_code == 201
        user_id = created.json()["id"]

        user_login = client.post(
            "/api/v1/auth/login",
            json={"username": "lifecycle-user", "password": "Lifecycle-Password-123!"},
        )
        assert user_login.status_code == 200
        user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}

        disabled = client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers=admin_headers,
            json={"active": False},
        )
        assert disabled.status_code == 200
        assert disabled.json()["active"] is False
        assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 401

        admin_me = client.get("/api/v1/auth/me", headers=admin_headers).json()
        self_disable = client.patch(
            f"/api/v1/admin/users/{admin_me['id']}/status",
            headers=admin_headers,
            json={"active": False},
        )
        assert self_disable.status_code == 409

        enabled = client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers=admin_headers,
            json={"active": True},
        )
        assert enabled.status_code == 200
        assert enabled.json()["active"] is True
