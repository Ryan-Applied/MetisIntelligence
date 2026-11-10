import pytest

from app.models import (
    Classification,
    Edition,
    Memory,
    MemoryType,
    Scope,
    ScopeError,
    ValidationStatus,
)


# -- scope invariants -------------------------------------------------------
def test_metis_scope_requires_tenant():
    with pytest.raises(ScopeError):
        Scope(edition=Edition.METIS, project="metis")


def test_core_scope_rejects_tenant():
    with pytest.raises(ScopeError):
        Scope(edition=Edition.CORE, tenant_id="client-x")


def test_repository_requires_project():
    with pytest.raises(ScopeError):
        Scope(edition=Edition.CORE, repository="repo-only")


# -- edition isolation (the hard boundary) ----------------------------------
def test_core_reader_cannot_read_metis_memory():
    core = Scope(edition=Edition.CORE, project="metis", repository="cyber-skill-extractor")
    metis_mem = Scope(edition=Edition.METIS, tenant_id="client-x", project="metis")
    assert core.can_read(metis_mem) is False


def test_metis_reader_cannot_read_other_tenant():
    reader = Scope(edition=Edition.METIS, tenant_id="client-a", project="metis")
    other = Scope(edition=Edition.METIS, tenant_id="client-b", project="metis")
    assert reader.can_read(other) is False


def test_metis_reader_reads_own_tenant_broader_scope():
    reader = Scope(edition=Edition.METIS, tenant_id="client-a",
                   project="metis", repository="engagement-1")
    org_mem = Scope(edition=Edition.METIS, tenant_id="client-a")  # broader
    assert reader.can_read(org_mem) is True


# -- downward inheritance ---------------------------------------------------
def test_repo_reader_inherits_org_memory():
    reader = Scope(edition=Edition.CORE, project="nexus", repository="api")
    org_mem = Scope(edition=Edition.CORE)  # org-wide
    assert reader.can_read(org_mem) is True


def test_narrow_memory_not_visible_to_broad_reader():
    reader = Scope(edition=Edition.CORE)  # org-wide reader
    repo_mem = Scope(edition=Edition.CORE, project="nexus", repository="api")
    assert reader.can_read(repo_mem) is False


# -- memory contract --------------------------------------------------------
def test_memory_computes_content_hash():
    m = Memory(type=MemoryType.PROCEDURAL, title="t", content="body",
               scope=Scope(edition=Edition.CORE, project="nexus"))
    assert m.content_hash.startswith("sha256:")


def test_with_content_bumps_version_and_rehashes():
    m = Memory(type=MemoryType.SEMANTIC, title="t", content="old",
               scope=Scope(edition=Edition.CORE))
    h0, v0 = m.content_hash, m.version
    m.with_content("new")
    assert m.version == v0 + 1
    assert m.content_hash != h0


def test_verified_classification_requires_verified_validation():
    with pytest.raises(ValueError):
        Memory(type=MemoryType.PROCEDURAL, title="t", content="c",
               scope=Scope(edition=Edition.CORE),
               classification=Classification.VERIFIED,
               validation_status=ValidationStatus.UNVALIDATED)


def test_confidence_bounds_enforced():
    with pytest.raises(ValueError):
        Memory(type=MemoryType.EPISODIC, title="t", content="c",
               scope=Scope(edition=Edition.CORE), confidence=1.5)
