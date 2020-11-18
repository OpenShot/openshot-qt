## How to contribute to OpenShot Video Editor

### Submitting an Issue (bug report)

* **Please check if this bug was already reported** by searching on GitHub under [Issues](https://github.com/OpenShot/openshot-qt/issues?q=+).

* If you're unable to find an existing report about the problem, [open a new issue](https://github.com/OpenShot/openshot-qt/issues/new?template=bug-report.md). Be sure to include a **title and clear description**, and fill in as much relevant information as possible. Include the steps to reproduce the crash or issue, and please note what operating system(s) you tried them on. (Some bugs only occur when using OpenShot on a particular OS.)

* Please **attach log files** if you are reporting a crash. Otherwise, we will not be able to determine the cause of the crash.

#### Reproducing a bug & collecting logs

1.  _Please download our latest daily installer:_
    <openshot.org/download#daily> - the latest builds are at the top of the list.
    (Use the buttons below the list to download installers for a different Operating System.)
2.  **Only if the bug involves video playback or Export**,
    or if you were asked to by the OpenShot developers, enable 'Debug Mode (Verbose)' in the Preferences.
    Debug Mode adds no additional information for user interface or project-editing bugs.
3.  Quit OpenShot and delete your log files, to ensure the files you submit contain only necessary information.
    (See below for logfile paths.)
4.  Re-launch OpenShot and trigger the problem as quickly as possible, then immediately quit the program.
    This helps keeps the log files small and relevant.
5.  Attach both log files to your issue.
    Github issue comments permit attaching `.log` files up to 2MB in size.
    You can insert the file(s) either by drag-and-drop, or using the link at the bottom of the comment edit field.
  
#### OpenShot log file locations  

##### Windows
*   OpenShot stores its logs in your user profile directory (`%USERPROFILE%`, e.g. `C:\Users\username\`)
    *   **<code><var>%USERPROFILE%</var>\\.openshot_qt\openshot-qt.log</code>**
    *   **<code><var>%USERPROFILE%</var>\\.openshot_qt\libopenshot.log</code>**

##### Linux/MacOS
*   OpenShot stores its logs in your home directory (`$HOME`, e.g. `/home/username/`)
    *   **<code><var>$HOME</var>/.openshot_qt/openshot-qt.log</code>**
    *   **<code><var>$HOME</var>/.openshot_qt/libopenshot.log</code>**

### Submitting a Pull Request (source code patch / bug fix)

1.  First, prepare your changes to submit as a Pull Request:

    1.  If necessary, register for a Github user account, and sign in.
    2.  Fork the project repository. (This will be done automatically if you use the web interface's "Edit file" links.)
    3.  Make your changes in a new branch based on `develop`. (If you edit on the website, you'll have the option to create and name a branch when you save your changes.)
    4.  Finally, open a new GitHub Pull Request from that branch.

2.  Ensure the PR description clearly describes the problem and your solution. If the patch is related to an existing issue report, include the issue number in your description. Github recognizes trigger phrases such as "fixes #1234" or "closes #9999", and will automatically link your PR with the referenced issue(s).

3.  After you submit your PR, a test build and various code-quality and style checks will be run on your branch, with the results displayed at the bottom of the page. Try to address any issues flagged by these checks, especially any issues with the test build. If OpenShot cannot be built successfully with your changes, the PR is blocked from being merged until the problem is resolved.

    Submitting "in-progress" code is fine, and can often be a good way to solicit feedback from other developers. Consider marking PRs that are unfinished or still under development with "WIP" at the start of the title, or convert the PR to draft status. This will indicate to the developers that your changes are not quite ready for inclusion in OpenShot.

OpenShot Video Editor is a volunteer effort, and a labor of love. Please be patient with any issues you find, and feel free to get involved and help us fix them!

Thanks!

OpenShot Team
