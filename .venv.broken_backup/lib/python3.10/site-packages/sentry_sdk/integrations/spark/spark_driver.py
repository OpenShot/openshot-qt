import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.utils import capture_internal_exceptions, ensure_integration_enabled

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from typing import Optional

    from sentry_sdk._types import Event, Hint
    from pyspark import SparkContext


class SparkIntegration(Integration):
    identifier = "spark"

    @staticmethod
    def setup_once() -> None:
        _setup_sentry_tracing()


def _set_app_properties() -> None:
    """
    Set properties in driver that propagate to worker processes, allowing for workers to have access to those properties.
    This allows worker integration to have access to app_name and application_id.
    """
    from pyspark import SparkContext

    spark_context = SparkContext._active_spark_context
    if spark_context:
        spark_context.setLocalProperty(
            "sentry_app_name",
            spark_context.appName,
        )
        spark_context.setLocalProperty(
            "sentry_application_id",
            spark_context.applicationId,
        )


def _start_sentry_listener(sc: "SparkContext") -> None:
    """
    Start java gateway server to add custom `SparkListener`
    """
    from pyspark.java_gateway import ensure_callback_server_started

    gw = sc._gateway
    ensure_callback_server_started(gw)
    listener = SentryListener()
    sc._jsc.sc().addSparkListener(listener)


def _add_event_processor(sc: "SparkContext") -> None:
    scope = sentry_sdk.get_isolation_scope()

    @scope.add_event_processor
    def process_event(event: "Event", hint: "Hint") -> "Optional[Event]":
        with capture_internal_exceptions():
            if sentry_sdk.get_client().get_integration(SparkIntegration) is None:
                return event

            if sc._active_spark_context is None:
                return event

            event.setdefault("user", {}).setdefault("id", sc.sparkUser())

            event.setdefault("tags", {}).setdefault(
                "executor.id", sc._conf.get("spark.executor.id")
            )
            event["tags"].setdefault(
                "spark-submit.deployMode",
                sc._conf.get("spark.submit.deployMode"),
            )
            event["tags"].setdefault("driver.host", sc._conf.get("spark.driver.host"))
            event["tags"].setdefault("driver.port", sc._conf.get("spark.driver.port"))
            event["tags"].setdefault("spark_version", sc.version)
            event["tags"].setdefault("app_name", sc.appName)
            event["tags"].setdefault("application_id", sc.applicationId)
            event["tags"].setdefault("master", sc.master)
            event["tags"].setdefault("spark_home", sc.sparkHome)

            event.setdefault("extra", {}).setdefault("web_url", sc.uiWebUrl)

        return event


def _activate_integration(sc: "SparkContext") -> None:
    _start_sentry_listener(sc)
    _set_app_properties()
    _add_event_processor(sc)


def _patch_spark_context_init() -> None:
    from pyspark import SparkContext

    spark_context_init = SparkContext._do_init

    @ensure_integration_enabled(SparkIntegration, spark_context_init)
    def _sentry_patched_spark_context_init(
        self: "SparkContext", *args: "Any", **kwargs: "Any"
    ) -> "Optional[Any]":
        rv = spark_context_init(self, *args, **kwargs)
        _activate_integration(self)
        return rv

    SparkContext._do_init = _sentry_patched_spark_context_init


def _setup_sentry_tracing() -> None:
    from pyspark import SparkContext

    if SparkContext._active_spark_context is not None:
        _activate_integration(SparkContext._active_spark_context)
        return
    _patch_spark_context_init()


class SparkListener:
    def onApplicationEnd(self, applicationEnd: "Any") -> None:  # noqa: N802,N803
        pass

    def onApplicationStart(self, applicationStart: "Any") -> None:  # noqa: N802,N803
        pass

    def onBlockManagerAdded(self, blockManagerAdded: "Any") -> None:  # noqa: N802,N803
        pass

    def onBlockManagerRemoved(self, blockManagerRemoved: "Any") -> None:  # noqa: N802,N803
        pass

    def onBlockUpdated(self, blockUpdated: "Any") -> None:  # noqa: N802,N803
        pass

    def onEnvironmentUpdate(self, environmentUpdate: "Any") -> None:  # noqa: N802,N803
        pass

    def onExecutorAdded(self, executorAdded: "Any") -> None:  # noqa: N802,N803
        pass

    def onExecutorBlacklisted(self, executorBlacklisted: "Any") -> None:  # noqa: N802,N803
        pass

    def onExecutorBlacklistedForStage(  # noqa: N802
        self,
        executorBlacklistedForStage: "Any",  # noqa: N803
    ) -> None:
        pass

    def onExecutorMetricsUpdate(self, executorMetricsUpdate: "Any") -> None:  # noqa: N802,N803
        pass

    def onExecutorRemoved(self, executorRemoved: "Any") -> None:  # noqa: N802,N803
        pass

    def onJobEnd(self, jobEnd: "Any") -> None:  # noqa: N802,N803
        pass

    def onJobStart(self, jobStart: "Any") -> None:  # noqa: N802,N803
        pass

    def onNodeBlacklisted(self, nodeBlacklisted: "Any") -> None:  # noqa: N802,N803
        pass

    def onNodeBlacklistedForStage(self, nodeBlacklistedForStage: "Any") -> None:  # noqa: N802,N803
        pass

    def onNodeUnblacklisted(self, nodeUnblacklisted: "Any") -> None:  # noqa: N802,N803
        pass

    def onOtherEvent(self, event: "Any") -> None:  # noqa: N802,N803
        pass

    def onSpeculativeTaskSubmitted(self, speculativeTask: "Any") -> None:  # noqa: N802,N803
        pass

    def onStageCompleted(self, stageCompleted: "Any") -> None:  # noqa: N802,N803
        pass

    def onStageSubmitted(self, stageSubmitted: "Any") -> None:  # noqa: N802,N803
        pass

    def onTaskEnd(self, taskEnd: "Any") -> None:  # noqa: N802,N803
        pass

    def onTaskGettingResult(self, taskGettingResult: "Any") -> None:  # noqa: N802,N803
        pass

    def onTaskStart(self, taskStart: "Any") -> None:  # noqa: N802,N803
        pass

    def onUnpersistRDD(self, unpersistRDD: "Any") -> None:  # noqa: N802,N803
        pass

    class Java:
        implements = ["org.apache.spark.scheduler.SparkListenerInterface"]


class SentryListener(SparkListener):
    def _add_breadcrumb(
        self,
        level: str,
        message: str,
        data: "Optional[dict[str, Any]]" = None,
    ) -> None:
        sentry_sdk.get_isolation_scope().add_breadcrumb(
            level=level, message=message, data=data
        )

    def onJobStart(self, jobStart: "Any") -> None:  # noqa: N802,N803
        sentry_sdk.get_isolation_scope().clear_breadcrumbs()

        message = "Job {} Started".format(jobStart.jobId())
        self._add_breadcrumb(level="info", message=message)
        _set_app_properties()

    def onJobEnd(self, jobEnd: "Any") -> None:  # noqa: N802,N803
        level = ""
        message = ""
        data = {"result": jobEnd.jobResult().toString()}

        if jobEnd.jobResult().toString() == "JobSucceeded":
            level = "info"
            message = "Job {} Ended".format(jobEnd.jobId())
        else:
            level = "warning"
            message = "Job {} Failed".format(jobEnd.jobId())

        self._add_breadcrumb(level=level, message=message, data=data)

    def onStageSubmitted(self, stageSubmitted: "Any") -> None:  # noqa: N802,N803
        stage_info = stageSubmitted.stageInfo()
        message = "Stage {} Submitted".format(stage_info.stageId())

        data = {"name": stage_info.name()}
        attempt_id = _get_attempt_id(stage_info)
        if attempt_id is not None:
            data["attemptId"] = attempt_id

        self._add_breadcrumb(level="info", message=message, data=data)
        _set_app_properties()

    def onStageCompleted(self, stageCompleted: "Any") -> None:  # noqa: N802,N803
        from py4j.protocol import Py4JJavaError  # type: ignore

        stage_info = stageCompleted.stageInfo()
        message = ""
        level = ""

        data = {"name": stage_info.name()}
        attempt_id = _get_attempt_id(stage_info)
        if attempt_id is not None:
            data["attemptId"] = attempt_id

        # Have to Try Except because stageInfo.failureReason() is typed with Scala Option
        try:
            data["reason"] = stage_info.failureReason().get()
            message = "Stage {} Failed".format(stage_info.stageId())
            level = "warning"
        except Py4JJavaError:
            message = "Stage {} Completed".format(stage_info.stageId())
            level = "info"

        self._add_breadcrumb(level=level, message=message, data=data)


def _get_attempt_id(stage_info: "Any") -> "Optional[int]":
    try:
        return stage_info.attemptId()
    except Exception:
        pass

    try:
        return stage_info.attemptNumber()
    except Exception:
        pass

    return None
