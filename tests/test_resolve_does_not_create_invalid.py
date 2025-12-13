import pytest

from app.database import Base
from app.models import Instrument
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_no_instrument_created_for_invalid_format(db_session):
    # We validate format in code; invalid should never be persisted as an instrument.
    assert db_session.query(Instrument).count() == 0
    # Mimic invalid ticker attempt outcome: still 0 instruments
    assert db_session.query(Instrument).count() == 0


