from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.config import Settings
from app.api.imports import get_import_service
from app.db.session import get_db_session
from app.main import create_app
from app.services.fake_gemini import FakeGeminiAdapter
from app.services.imports import ImportService
from app.services.menu_extraction import MenuExtractionService


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return get_settings().database_url


@pytest.fixture(scope="session", autouse=True)
def migrated_database(test_database_url: str) -> Iterator[None]:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", test_database_url)
    command.upgrade(config, "head")
    yield
    command.downgrade(config, "base")


@pytest_asyncio.fixture
async def db_session(test_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(text("TRUNCATE import_events, extracted_menus, imports RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
def app(db_session: AsyncSession) -> Iterator:
    app = create_app()

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    def override_get_import_service() -> ImportService:
        settings = Settings(gemini_use_fake=True)
        return ImportService(
            db_session,
            menu_extraction_service=MenuExtractionService(
                adapter=FakeGeminiAdapter(),
                settings=settings,
            ),
        )

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_import_service] = override_get_import_service
    yield app
    app.dependency_overrides.clear()
