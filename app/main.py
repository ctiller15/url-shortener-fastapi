from contextlib import asynccontextmanager
from typing import Annotated, Union

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import Result
from sqlmodel import Field, SQLModel, create_engine, Session, text


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

app = FastAPI()


class CreateURLBody(BaseModel):
    long_url: str
    custom_alias: Union[str, None] = None

# every single long url should be unique to save on space.


class Urls(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    short_url: str | None = Field(default=None, index=True, nullable=True)
    long_url: str = Field(unique=True)


class CustomAliases(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    url_id: int = Field(index=True, foreign_key='urls.id')
    alias: str | None = Field(index=True)


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def encode_numeric_id(num: int) -> str:
    BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if num == 0:
        return BASE62[0]

    arr = []
    base = len(BASE62)

    while num != 0:
        num, rem = divmod(num, base)
        arr.append(BASE62[rem])

    arr.reverse()
    return ''.join(arr)


@app.post("/urls")
def create_url(body: CreateURLBody, session: SessionDep):
    short_id = None

    q = text("INSERT OR IGNORE INTO urls(long_url) "
             "VALUES(:long_url) "
             "RETURNING *;")

    result: Result = session.exec(
        statement=q, params={"long_url": body.long_url})

    rows_modified = result.mappings().all()

    if len(rows_modified) > 0:
        row_id = rows_modified[0]['id']

        short_id = encode_numeric_id(row_id)

        q = text("UPDATE urls "
                 "SET short_url = :short_id "
                 "WHERE id = :row_id;")

        result: Result = session.exec(
            statement=q, params={"short_id": short_id, "row_id": row_id})

        session.commit()

    if body.custom_alias:
        q = text("SELECT id "
                 "FROM urls "
                 "WHERE long_url = :long_url "
                 "LIMIT 1;")

        result: Result = session.exec(
            statement=q, params={"long_url": body.long_url})

        result_row = result.mappings().first()
        url_id = result_row['id']

        q = text("INSERT INTO customaliases(url_id, alias) "
                 "VALUES(:url_id, :alias)"
                 "RETURNING *;")

        result: Result = session.exec(
            statement=q, params={"url_id": url_id, "alias": body.custom_alias}
        )

        result_row = result.mappings().first()
        custom_alias = result_row['alias']

        session.commit()

        return {
            "short_id": short_id,
            "custom_alias": custom_alias,
        }
    else:
        # If we never retrieved a short id, we should just fetch and return it.
        if not short_id:
            q = text("SELECT short_url "
                     "FROM urls "
                     "WHERE long_url = :long_url")

            result: Result = session.exec(
                statement=q, params={"long_url": body.long_url}
            )

            row = result.mappings().first()
            short_id = row['short_url']
        return {
            "short_id": short_id,
        }


@app.get("/urls/{short_url}")
def get_url(short_url: str, session: SessionDep):

    get_by_short_url = text("SELECT long_url "
                            "FROM urls "
                            "WHERE short_url = :short_url "
                            "LIMIT 1")

    query_result: Result = session.exec(
        statement=get_by_short_url, params={"short_url": short_url}
    )

    result = query_result.mappings().first()

    try:
        long_url = result["long_url"]
    except TypeError:
        raise HTTPException(status_code=404, detail="shortlink not found")

    return {
        "long_url": long_url
    }
