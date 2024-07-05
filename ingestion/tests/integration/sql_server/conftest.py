import os
import shutil
from typing import cast

import pytest
from sqlalchemy import create_engine, text
from testcontainers.mssql import SqlServerContainer

from metadata.generated.schema.api.services.createDatabaseService import (
    CreateDatabaseServiceRequest,
)
from metadata.generated.schema.entity.services.connections.database.mssqlConnection import (
    MssqlScheme,
    MssqlConnection,
)
from metadata.generated.schema.entity.services.databaseService import (
    DatabaseService,
    DatabaseServiceType,
    DatabaseConnection,
)
from ...helpers.docker_utils import try_bind


@pytest.fixture(scope="session")
def mssql_container(tmp_path_factory):
    container = SqlServerContainer(
        "mcr.microsoft.com/mssql/server:2017-latest", dbname="AdventureWorks"
    )
    data_dir = tmp_path_factory.mktemp("data")
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "data", "AdventureWorks2017.bak"),
        str(data_dir),
    )
    with open(data_dir / "install.sql", "w") as f:
        f.write(
            """
USE [master]
RESTORE DATABASE [AdventureWorks]
    FROM DISK = '/data/AdventureWorks2017.bak'
        WITH MOVE 'AdventureWorks2017' TO '/var/opt/mssql/data/AdventureWorks.mdf',
        MOVE 'AdventureWorks2017_log' TO '/var/opt/mssql/data/AdventureWorks_log.ldf'
GO
        """
        )

    container.volumes = {str(data_dir): {"bind": "/data"}}
    with try_bind(container, 1433, 1433) as container:
        docker_container = container.get_wrapped_container()
        res = docker_container.exec_run(
            [
                "/opt/mssql-tools/bin/sqlcmd",
                "-S",
                "localhost",
                "-U",
                container.username,
                "-P",
                container.password,
                "-d",
                "master",
                "-i",
                "/data/install.sql",
            ]
        )
        if res[0] != 0:
            raise Exception("Failed to create mssql database:" + res[1].decode("utf-8"))
        engine = create_engine(
            "mssql+pytds://" + container.get_connection_url().split("://")[1],
            connect_args={"autocommit": True},
        )
        with engine.connect() as conn:
            transaciton = conn.begin()
            conn.execute(
                text(
                    "SELECT * INTO AdventureWorks.HumanResources.DepartmenCopy FROM AdventureWorks.HumanResources.Department;"
                )
            )
            transaciton.commit()
        yield container


@pytest.fixture(
    params=[
        MssqlScheme.mssql_pytds,
        MssqlScheme.mssql_pyodbc,
    ],
)
def scheme(request):
    return request.param


@pytest.fixture()
def create_service_request(mssql_container, scheme, tmp_path_factory):
    return CreateDatabaseServiceRequest(
        name="docker_test_" + tmp_path_factory.mktemp("mssql").name + "_" + scheme.name,
        serviceType=DatabaseServiceType.Mssql,
        connection=DatabaseConnection(
            config=MssqlConnection(
                username=mssql_container.username,
                password=mssql_container.password,
                hostPort="localhost:"
                + mssql_container.get_exposed_port(mssql_container.port),
                database="AdventureWorks",
                scheme=scheme,
                ingestAllDatabases=True,
                connectionOptions={"TrustServerCertificate": "yes"},
            )
        ),
    )


@pytest.fixture()
def ingestion_config(
    db_service, tmp_path_factory, workflow_config, sink_config, patch_password
):
    return {
        "source": {
            "type": "mssql",
            "serviceName": db_service.fullyQualifiedName.root,
            "serviceConnection": db_service.connection.dict(),
            "sourceConfig": {
                "config": {
                    "type": "DatabaseMetadata",
                    "databaseFilterPattern": {"includes": ["TestDB", "AdventureWorks"]},
                },
            },
        },
        "sink": sink_config,
        "workflowConfig": workflow_config,
    }


@pytest.fixture()
def patch_password(mssql_container):
    def inner(service: DatabaseService):
        service.connection.config = cast(MssqlConnection, service.connection.config)
        service.connection.config.password = type(service.connection.config.password)(
            mssql_container.password
        )
        return service

    return inner
