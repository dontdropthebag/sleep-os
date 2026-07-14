import io
import zipfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSession()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ------------------------------------------------------------------
# Synthetic Sleep as Android fixtures (no real personal data)
# ------------------------------------------------------------------
SAA_HEADER = ("Id,Tz,From,To,Sched,Hours,Rating,Comment,Framerate,Snore,Noise,"
              "Cycles,DeepSleep,LenAdjust,Geo")


def saa_record(record_id: str, tz: str, start: datetime, end: datetime, *,
               hours: float | None = None, rating: str = "4,0", comment: str = "",
               snore: str = "-1", noise: str = "-1", cycles: str = "5",
               deep: str = "0,35", events: list[str] | None = None,
               movement: list[float] | None = None) -> str:
    fmt = "%d. %m. %Y %H:%M"
    hours_s = str(hours).replace(".", ",") if hours is not None else "-1"
    time_cols, move_cells = [], []
    if movement:
        t = start
        for v in movement:
            time_cols.append(f'"{t.strftime("%H:%M")}"')
            move_cells.append(f'"{str(v).replace(".", ",")}"')
            t += timedelta(minutes=10)
    event_hdr = ",".join(['"Event"'] * len(events or []))
    event_cells = ",".join(f'"{e}"' for e in (events or []))
    header = SAA_HEADER + ("," + ",".join(time_cols) if time_cols else "") + \
        ("," + event_hdr if events else "")
    data = ",".join([
        f'"{record_id}"', f'"{tz}"', f'"{start.strftime(fmt)}"', f'"{end.strftime(fmt)}"',
        f'"{end.strftime(fmt)}"', f'"{hours_s}"', f'"{rating}"', f'"{comment}"',
        '"10000"', f'"{snore}"', f'"{noise}"', f'"{cycles}"', f'"{deep}"', '"0"', '""',
    ] + move_cells) + ("," + event_cells if events else "")
    return header + "\n" + data + "\n"


def make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def epoch_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)
