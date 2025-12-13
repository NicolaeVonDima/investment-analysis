import os
from datetime import date

import pytest

from app.database import Base
from app.models import Instrument, PriceEOD
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError


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


def test_price_eod_unique_instrument_date(db_session):
    inst = Instrument(canonical_symbol="ADBE")
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)

    db_session.add(PriceEOD(instrument_id=inst.id, as_of_date=date(2025, 12, 12), close=1.0, adjusted_close=1.0))
    db_session.commit()

    db_session.add(PriceEOD(instrument_id=inst.id, as_of_date=date(2025, 12, 12), close=2.0, adjusted_close=2.0))
    with pytest.raises(IntegrityError):
        db_session.commit()


