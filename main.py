import os

import uvicorn
from fastapi import FastAPI
from libcloud.storage.drivers.local import LocalStorageDriver
from sqlalchemy_file.storage import StorageManager
from mysite.chain import agent
from mysite.api import  info, check
from mysite.db.db import Base, engine


Base.metadata.create_all(bind=engine)

app = FastAPI(title="HR resume checker")
app.include_router(info.router)
app.include_router(agent.agent_router)
app.include_router(check.check_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)