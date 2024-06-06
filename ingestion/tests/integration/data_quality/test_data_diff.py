import pytest
from pydantic import BaseModel
from sqlalchemy import VARBINARY
from sqlalchemy import Column as SQAColumn
from sqlalchemy import MetaData
from sqlalchemy import Table as SQATable
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.sql import sqltypes

from metadata.data_quality.api.models import (
    TestCaseDefinition,
    TestSuiteProcessorConfig,
)
from metadata.generated.schema.api.services.createDatabaseService import (
    CreateDatabaseServiceRequest,
)
from metadata.generated.schema.entity.data.table import Table
from metadata.generated.schema.entity.services.connections.database.common.basicAuth import (
    BasicAuth,
)
from metadata.generated.schema.entity.services.connections.database.postgresConnection import (
    PostgresConnection,
)
from metadata.generated.schema.entity.services.databaseService import (
    DatabaseConnection,
    DatabaseService,
    DatabaseServiceType,
)
from metadata.generated.schema.metadataIngestion.testSuitePipeline import (
    TestSuiteConfigType,
    TestSuitePipeline,
)
from metadata.generated.schema.metadataIngestion.workflow import (
    LogLevels,
    OpenMetadataWorkflowConfig,
    Processor,
    Sink,
    Source,
    SourceConfig,
    WorkflowConfig,
)
from metadata.generated.schema.tests.basic import TestCaseResult, TestCaseStatus
from metadata.generated.schema.tests.testCase import TestCase, TestCaseParameterValue
from metadata.generated.schema.tests.testDefinition import (
    EntityType,
    TestCaseParameterDefinition,
    TestDataType,
    TestDefinition,
    TestPlatform,
)
from metadata.ingestion.models.custom_pydantic import CustomSecretStr
from metadata.ingestion.ometa.ometa_api import OpenMetadata
from metadata.workflow.data_quality import TestSuiteWorkflow
from metadata.workflow.metadata import MetadataWorkflow


class TestParameters(BaseModel):
    test_case_defintion: TestCaseDefinition
    table2_fqn: str
    expected: TestCaseResult

    def __init__(self, *args, **kwargs):
        if args:
            # Map positional arguments to fields
            field_names = list(self.__annotations__.keys())
            kwargs.update(dict(zip(field_names, args)))

        super().__init__(**kwargs)


@pytest.mark.parametrize(
    "parameters",
    [
        pytest.param(TestParameters(*t), id=t[0].name)
        for t in [
            (
                TestCaseDefinition(
                    name="compare_same_tables",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(
                            name="keyColumns", value="['customer_id']"
                        ),
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Success,
                    failedRows=0,
                    passedRows=599,
                ),
            ),
            (
                TestCaseDefinition(
                    name="with_explicit_key_columns",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(
                            name="keyColumns", value="['customer_id']"
                        ),
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Failed,
                    failedRows=321,
                    passedRows=278,
                ),
            ),
            (
                TestCaseDefinition(
                    name="resolve_primary_keys",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[],
                ),
                "POSTGRES_SERVICE.dvdrental.public.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Failed,
                    failedRows=321,
                    passedRows=278,
                ),
            ),
            (
                TestCaseDefinition(
                    name="with_passing_threshold",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(name="threshold", value="322"),
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Success,
                    passedRows=278,
                    failedRows=321,
                ),
            ),
            (
                TestCaseDefinition(
                    name="with_failing_threshold",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(name="threshold", value="321"),
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Failed,
                    passedRows=278,
                    failedRows=321,
                ),
            ),
            (
                TestCaseDefinition(
                    name="with_where_clause",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(
                            name="where",
                            value="MOD(customer_id, 2) != 0 AND MOD(customer_id, 13) != 0",
                        ),
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Success,
                ),
            ),
            (
                TestCaseDefinition(
                    name="without_first_name",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[],
                ),
                "POSTGRES_SERVICE.dvdrental.public.customer_without_first_name",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Failed,
                ),
            ),
            (
                TestCaseDefinition(
                    name="without_first_name_with_extra_column",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(
                            name="useColumns", value="['last_name', 'email']"
                        )
                    ],
                ),
                "POSTGRES_SERVICE.dvdrental.public.customer_without_first_name",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Success,
                ),
            ),
            (
                TestCaseDefinition(
                    name="postgres_vs_mysql_success",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[
                        TestCaseParameterValue(
                            name="useColumns",
                            value=str(
                                [
                                    "store_id",
                                    "first_name",
                                    "last_name",
                                    "email",
                                    "activebool",
                                    "address_id",
                                    "active",
                                    # "create_date", # date types are incomparable for mysql and postgres
                                    "last_update",
                                ]
                            ),
                        )
                    ],
                ),
                "MYSQL_SERVICE.default.test.customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Success,
                ),
            ),
            (
                TestCaseDefinition(
                    name="postgres_vs_mysql_failure",
                    testDefinitionName="tableDiff",
                    computePassedFailedRowCount=True,
                    parameterValues=[],
                ),
                "MYSQL_SERVICE.default.test.changed_customer",
                TestCaseResult(
                    testCaseStatus=TestCaseStatus.Failed,
                ),
            ),
        ]
    ],
)
def test_happy_paths(
    postgres_service: DatabaseService,
    prepare_data,
    ingest_postgres_metadata,
    ingest_mysql_service,
    metadata,
    parameters: TestParameters,
):
    table1 = metadata.get_by_name(
        Table,
        f"{postgres_service.fullyQualifiedName.root}.dvdrental.public.customer",
        nullable=False,
    )
    table2_service_name = parameters.table2_fqn.split(".")[0]
    table2_service = {
        "POSTGRES_SERVICE": postgres_service,
        "MYSQL_SERVICE": ingest_mysql_service,
    }[table2_service_name]
    parameters.table2_fqn = parameters.table2_fqn.replace(
        table2_service_name, table2_service.fullyQualifiedName.root
    )
    service2_password = getattr(
        table2_service.connection.config, "authType", table2_service.connection.config
    ).password.get_secret_value()
    parameters.test_case_defintion.parameterValues.extend(
        [
            TestCaseParameterValue(
                name="table2",
                value=parameters.table2_fqn,
            ),
            TestCaseParameterValue(
                # we need to build the service url explicitly bc there is currently no
                # way to get passwords from the integration test environment
                name="service2Url",
                value=str(
                    URL.create(
                        drivername=table2_service.connection.config.scheme.value.split(
                            "+"
                        )[0],
                        username=table2_service.connection.config.username,
                        password=service2_password,
                        host=table2_service.connection.config.hostPort.split(":")[0],
                        port=int(
                            table2_service.connection.config.hostPort.split(":")[1]
                        ),
                        database=getattr(
                            table2_service.connection.config,
                            "databaseSchema",
                            None,
                        )
                        or table2_service.connection.config.database,
                    )
                ),
            ),
        ]
    )

    workflow_config = OpenMetadataWorkflowConfig(
        source=Source(
            type=TestSuiteConfigType.TestSuite.value,
            serviceName="MyTestSuite",
            sourceConfig=SourceConfig(
                config=TestSuitePipeline(
                    type=TestSuiteConfigType.TestSuite,
                    entityFullyQualifiedName=f"{table1.fullyQualifiedName.root}",
                )
            ),
            serviceConnection=postgres_service.connection,
        ),
        processor=Processor(
            type="orm-test-runner",
            config={"testCases": [parameters.test_case_defintion]},
        ),
        sink=Sink(
            type="metadata-rest",
            config={},
        ),
        workflowConfig=WorkflowConfig(
            loggerLevel=LogLevels.DEBUG, openMetadataServerConfig=metadata.config
        ),
    )

    test_suite_procesor = TestSuiteWorkflow.create(workflow_config)
    test_suite_procesor.execute()
    test_suite_procesor.stop()
    test_case_entity: TestCase = metadata.get_or_create_test_case(
        f"{table1.fullyQualifiedName.root}.{parameters.test_case_defintion.name}"
    )
    try:
        test_suite_procesor.raise_from_status()
    finally:
        metadata.delete(TestCase, test_case_entity.id, recursive=True, hard_delete=True)
    assert "ERROR: Unexpected error" not in test_case_entity.testCaseResult.result
    assert_equal_pydantic_objects(parameters.expected, test_case_entity.testCaseResult)


def assert_equal_pydantic_objects(
    expected: BaseModel, actual: BaseModel, ignore_none=True
):
    for key, value in expected.dict().items():
        if value is not None and ignore_none:
            if not value == actual.dict()[key]:
                # an explicit AssertionError because PyCharm does not handle helper functions well:
                # https://youtrack.jetbrains.com/issue/PY-51929/pytest-assertion-information-not-printed-in-certain-situations#focus=Comments-27-8459641.0-0
                raise AssertionError(
                    f"objects mismatched on field: [{key}], expected: [{value}], actual: [{actual.dict()[key]}]"
                )


@pytest.mark.parametrize(
    "parameters,expected",
    [
        pytest.param(
            None,
            None,
            marks=pytest.mark.skip(
                reason="TODO: implement test - columns with different data types"
            ),
        ),
        pytest.param(
            None,
            None,
            marks=pytest.mark.skip(reason="TODO: implement test - different columns"),
        ),
        pytest.param(
            None,
            None,
            marks=pytest.mark.skip(
                reason="TODO: implement test - table1 does not exist"
            ),
        ),
        pytest.param(
            None,
            None,
            marks=pytest.mark.skip(
                reason="TODO: implement test - table2 does not exist"
            ),
        ),
        pytest.param(
            None,
            None,
            marks=pytest.mark.skip(
                reason="TODO: implement test - where clause is invalid"
            ),
        ),
    ],
)
def test_error_paths(parameters, expected):
    pass


@pytest.fixture(scope="module")
def postgres_service(metadata, postgres_container):
    service = CreateDatabaseServiceRequest(
        name="docker_test_postgres_db",
        serviceType=DatabaseServiceType.Postgres,
        connection=DatabaseConnection(
            config=PostgresConnection(
                username=postgres_container.username,
                authType=BasicAuth(password=postgres_container.password),
                hostPort="localhost:"
                + postgres_container.get_exposed_port(postgres_container.port),
                database="dvdrental",
            )
        ),
    )
    service_entity = metadata.create_or_update(data=service)
    service_entity.connection.config.authType.password = CustomSecretStr(
        postgres_container.password
    )
    yield service_entity
    metadata.delete(
        DatabaseService, service_entity.id, recursive=True, hard_delete=True
    )


@pytest.fixture(scope="module")
def ingest_postgres_metadata(postgres_service, metadata: OpenMetadata):
    workflow_config = OpenMetadataWorkflowConfig(
        source=Source(
            type=postgres_service.connection.config.type.value.lower(),
            serviceName=postgres_service.fullyQualifiedName.root,
            serviceConnection=postgres_service.connection,
            sourceConfig=SourceConfig(config={}),
        ),
        sink=Sink(
            type="metadata-rest",
            config={},
        ),
        workflowConfig=WorkflowConfig(openMetadataServerConfig=metadata.config),
    )
    metadata_ingestion = MetadataWorkflow.create(workflow_config)
    metadata_ingestion.execute()
    metadata_ingestion.raise_from_status()
    return


@pytest.fixture(scope="module")
def create_table_diff_test_defintion(metadata):
    test_definition = metadata.get_or_create_test_definition(
        test_definition_fqn="tableDiff",
        test_definition_description="A demo custom test",
        entity_type=EntityType.TABLE,
        test_platforms=[TestPlatform.OpenMetadata],
        test_case_parameter_definition=[
            TestCaseParameterDefinition(
                name="table2FQN", dataType=TestDataType.STRING, required=True
            ),
            TestCaseParameterDefinition(
                name="service2Url", dataType=TestDataType.STRING
            ),
            TestCaseParameterDefinition(
                name="keyColumns", dataType=TestDataType.STRING
            ),
            TestCaseParameterDefinition(name="threshold", dataType=TestDataType.INT),
            TestCaseParameterDefinition(name="updateColumn", dataType=TestDataType.INT),
            TestCaseParameterDefinition(name="useColumns", dataType=TestDataType.INT),
        ],
    )
    yield
    metadata.delete(
        TestDefinition, test_definition.id, recursive=True, hard_delete=True
    )


def add_changed_tables(connection: Connection):
    connection.execute("CREATE TABLE customer_200 AS SELECT * FROM customer LIMIT 200;")
    connection.execute("CREATE TABLE changed_customer AS SELECT * FROM customer;")
    connection.execute(
        "UPDATE changed_customer SET first_name = 'John' WHERE MOD(customer_id, 2) = 0;"
    )
    connection.execute("DELETE FROM changed_customer WHERE MOD(customer_id, 13) = 0;")
    connection.execute(
        "CREATE TABLE customer_without_first_name AS SELECT * FROM customer;"
    )
    connection.execute(
        "ALTER TABLE customer_without_first_name DROP COLUMN first_name;"
    )


@pytest.fixture(scope="module")
def prepare_data(postgres_container, mysql_container):
    postgres_engine = create_engine(
        make_url(postgres_container.get_connection_url()).set(database="dvdrental")
    )
    with postgres_engine.connect() as conn:
        add_changed_tables(conn)
    mysql_container = create_engine(
        make_url(mysql_container.get_connection_url()).set(
            database=mysql_container.dbname
        )
    )
    postgres_engine = create_engine(
        make_url(postgres_container.get_connection_url()).set(database="dvdrental")
    )
    copy_table(postgres_engine, mysql_container, "customer")
    copy_table(postgres_engine, mysql_container, "changed_customer")


def copy_table(source_engine, destination_engine, table_name):
    source_metadata = MetaData()
    source_table = SQATable(table_name, source_metadata, autoload_with=source_engine)
    destination_metadata = MetaData()
    destination_table = SQATable(table_name, destination_metadata)

    for column in source_table.columns:
        # we copy all the columns without constraints, indexes or defaults
        # as we are only interested in the data
        if (
            isinstance(column.type, postgresql.base.BYTEA)
            and destination_engine.dialect.name == "mssql"
        ):
            column_copy = SQAColumn(column.name, VARBINARY)
        elif (
            isinstance(column.type, sqltypes.BOOLEAN)
            and destination_engine.dialect.name == "mssql"
        ):
            column_copy = SQAColumn(column.name, sqltypes.Boolean)
        elif (
            isinstance(column.type, sqltypes.TIMESTAMP)
            and destination_engine.dialect.name == "mssql"
        ):
            column_copy = SQAColumn(column.name, sqltypes.DateTime)
        elif (
            isinstance(column.type, sqltypes.DATE)
            and destination_engine.dialect.name == "mssql"
        ):
            column_copy = SQAColumn(column.name, sqltypes.DateTime)
        else:
            column_copy = SQAColumn(column.name, column.type)
        destination_table.append_column(column_copy)
    destination_metadata.create_all(destination_engine)
    with source_engine.connect() as source_connection, destination_engine.connect() as destination_connection:
        data = source_connection.execute(source_table.select()).fetchall()
        batch_size = 1000
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            destination_connection.execute(
                source_table.insert(), [dict(row) for row in batch]
            )
