import asyncio


async def asyncRetry(apiCall, options=None):
    """
    Retry an asynchronous API call multiple times with configurable options.

    :param apiCall: The asynchronous function to be retried.
    :param options: An optional dictionary that allows you to configure the retry behavior.
                    It has the following properties:
                    - maxRetries: The maximum number of retries before giving up (default is 1).
                    - delayInSeconds: The delay in seconds between each retry attempt (default is 1).
                    - callback: A function that will be called after each failed attempt.
    :return: The result of the successful API call.

    This function retries an asynchronous API call multiple times with configurable options.
    It attempts to execute the `apiCall` and returns the result if successful. If the `apiCall`
    raises an exception, it calls the `callback` function (if provided), introduces a delay
    before the next retry attempt, and continues retrying until the maximum number of retries
    is reached. If all retry attempts are exhausted and the `apiCall` still fails, it raises
    the last encountered exception.

    Example:
        async def myApiCall():
            # API call logic here
            ...

        result = await asyncRetry(myApiCall, options={
            'maxRetries': 3,
            'delayInSeconds': 1,
            'callback': lambda: print('Retry attempt failed')
        })
        print(result)
    """
    if options is None:
        options = {}
    delayInSeconds = options.get("delayInSeconds", 1)
    callback = options.get("callback")
    maxRetries = options.get("maxRetries", 1)

    for attempt in range(maxRetries):
        try:
            return await apiCall()
        except Exception as error:
            if callback:
                callback()
            if attempt < maxRetries - 1:
                await asyncio.sleep(delayInSeconds)
            else:
                raise error


async def asyncRetryGather(apiCalls, options=None):
    """
    Retry multiple asynchronous API calls concurrently with configurable options.

    :param apiCalls: A list of asynchronous functions to be retried.
    :param options: An optional dictionary that allows you to configure the retry behavior.
                    It has the following properties:
                    - maxRetries: The maximum number of retries before giving up (default is 1).
                    - delayInSeconds: The delay in seconds between each retry attempt (default is 1).
                    - callback: A function that will be called after each failed attempt.
    :return: A list of results from the successful API calls.

    This function retries multiple asynchronous API calls concurrently with configurable options.
    It creates tasks for each `apiCall` and executes them concurrently using `asyncio.gather()`.
    Each task represents the execution of `asyncRetry` for a single `apiCall`. The results of
    each successful API call are returned as a list in the same order as the input `apiCalls`.

    Example:
        async def myApiCall1():
            # API call logic here
            ...

        async def myApiCall2():
            # API call logic here
            ...

        results = await asyncRetryGather([myApiCall1, myApiCall2], options={
            'maxRetries': 3,
            'delayInSeconds': 1,
            'callback': lambda: print('Retry attempt failed')
        })
        print(results)
    """
    if options is None:
        options = {}
    delayInSeconds = options.get("delayInSeconds", 1)
    callback = options.get("callback")
    maxRetries = options.get("maxRetries", 1)

    tasks = []
    for apiCall in apiCalls:
        task = asyncio.create_task(asyncRetry(apiCall, options))
        tasks.append(task)
    return await asyncio.gather(*tasks)
