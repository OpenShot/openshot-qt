#define UNICODE
#define _UNICODE
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static void write_log(HANDLE log, const wchar_t *message)
{
    DWORD written = 0;
    char utf8[8192];
    int length = WideCharToMultiByte(CP_UTF8, 0, message, -1, utf8, sizeof(utf8), NULL, NULL);
    if (length > 1) {
        WriteFile(log, utf8, (DWORD)(length - 1), &written, NULL);
    }
}

static void write_error(HANDLE log, const wchar_t *operation, DWORD code)
{
    wchar_t system_message[2048] = L"";
    wchar_t line[4096];
    FormatMessageW(
        FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL, code, 0, system_message, ARRAYSIZE(system_message), NULL);
    swprintf(line, ARRAYSIZE(line), L"%ls failed: Win32=%lu (0x%08lX) %ls\r\n",
             operation, code, code, system_message);
    write_log(log, line);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show)
{
    wchar_t module_path[32768];
    wchar_t package_dir[32768];
    wchar_t target_path[32768];
    wchar_t local_app_data[32768];
    wchar_t log_dir[32768];
    wchar_t log_path[32768];
    wchar_t line[65536];
    DWORD module_length;
    HANDLE log;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    DWORD child_exit = 0;
    SYSTEMTIME now;
    UINT32 package_name_length = 0;
    LONG package_result;

    (void)instance;
    (void)previous;
    (void)arguments;
    (void)show;

    module_length = GetModuleFileNameW(NULL, module_path, ARRAYSIZE(module_path));
    if (!module_length || module_length >= ARRAYSIZE(module_path)) {
        return (int)GetLastError();
    }
    wcscpy(package_dir, module_path);
    wchar_t *separator = wcsrchr(package_dir, L'\\');
    if (!separator) {
        return ERROR_BAD_PATHNAME;
    }
    *separator = L'\0';
    swprintf(target_path, ARRAYSIZE(target_path), L"%ls\\openshot-qt-cli.exe", package_dir);

    DWORD app_data_length = GetEnvironmentVariableW(
        L"LOCALAPPDATA", local_app_data, ARRAYSIZE(local_app_data));
    if (!app_data_length || app_data_length >= ARRAYSIZE(local_app_data)) {
        return (int)GetLastError();
    }
    swprintf(log_dir, ARRAYSIZE(log_dir), L"%ls\\OpenShot Video Editor", local_app_data);
    CreateDirectoryW(log_dir, NULL);
    swprintf(log_path, ARRAYSIZE(log_path), L"%ls\\msix-startup.log", log_dir);

    SECURITY_ATTRIBUTES security = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    log = CreateFileW(
        log_path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
        &security, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (log == INVALID_HANDLE_VALUE) {
        return (int)GetLastError();
    }
    SetFilePointer(log, 0, NULL, FILE_END);

    GetSystemTime(&now);
    swprintf(line, ARRAYSIZE(line),
             L"\r\n=== OpenShot MSIX diagnostic launch %04u-%02u-%02uT%02u:%02u:%02u.%03uZ ===\r\n",
             now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute,
             now.wSecond, now.wMilliseconds);
    write_log(log, line);
    swprintf(line, ARRAYSIZE(line), L"Launcher: %ls\r\nPackage directory: %ls\r\nTarget: %ls\r\nLog: %ls\r\n",
             module_path, package_dir, target_path, log_path);
    write_log(log, line);

    package_result = GetCurrentPackageFullName(&package_name_length, NULL);
    if (package_result == ERROR_INSUFFICIENT_BUFFER) {
        wchar_t *package_name = HeapAlloc(
            GetProcessHeap(), HEAP_ZERO_MEMORY, package_name_length * sizeof(wchar_t));
        if (package_name) {
            package_result = GetCurrentPackageFullName(&package_name_length, package_name);
            if (package_result == ERROR_SUCCESS) {
                swprintf(line, ARRAYSIZE(line), L"Package identity: %ls\r\n", package_name);
                write_log(log, line);
            } else {
                write_error(log, L"GetCurrentPackageFullName", (DWORD)package_result);
            }
            HeapFree(GetProcessHeap(), 0, package_name);
        }
    } else {
        write_error(log, L"GetCurrentPackageFullName", (DWORD)package_result);
    }

    DWORD attributes = GetFileAttributesW(target_path);
    if (attributes == INVALID_FILE_ATTRIBUTES) {
        write_error(log, L"GetFileAttributes(openshot-qt-cli.exe)", GetLastError());
        CloseHandle(log);
        return ERROR_FILE_NOT_FOUND;
    }
    swprintf(line, ARRAYSIZE(line), L"Target attributes: 0x%08lX\r\n", attributes);
    write_log(log, line);

    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput = log;
    startup.hStdError = log;
    SetEnvironmentVariableW(L"OPENSHOT_MSIX_DIAGNOSTICS", L"1");
    SetEnvironmentVariableW(L"PYTHONFAULTHANDLER", L"1");
    SetEnvironmentVariableW(L"QT_DEBUG_PLUGINS", L"1");
    write_log(log, L"Calling CreateProcessW...\r\n");
    if (!CreateProcessW(
            target_path, NULL, NULL, NULL, TRUE, CREATE_UNICODE_ENVIRONMENT,
            NULL, package_dir, &startup, &process)) {
        DWORD error_code = GetLastError();
        write_error(log, L"CreateProcessW(openshot-qt-cli.exe)", error_code);
        CloseHandle(log);
        return (int)error_code;
    }

    swprintf(line, ARRAYSIZE(line), L"Child created successfully: PID=%lu TID=%lu\r\n",
             process.dwProcessId, process.dwThreadId);
    write_log(log, line);
    WaitForSingleObject(process.hProcess, INFINITE);
    if (!GetExitCodeProcess(process.hProcess, &child_exit)) {
        write_error(log, L"GetExitCodeProcess", GetLastError());
    } else {
        swprintf(line, ARRAYSIZE(line), L"Child exit: unsigned=%lu hex=0x%08lX signed=%ld\r\n",
                 child_exit, child_exit, (LONG)child_exit);
        write_log(log, line);
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    write_log(log, L"=== Diagnostic launcher finished ===\r\n");
    CloseHandle(log);
    return (int)child_exit;
}
