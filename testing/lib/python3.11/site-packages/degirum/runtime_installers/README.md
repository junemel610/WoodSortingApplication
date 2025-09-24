```
For each runtime that has installation steps that are able to be made PUBLIC to the end user
(runtime files and installation steps are publicly available, no internal libraries are used), we create:
- directory for the runtime named <runtime>
- install_<runtime>.sh/bat script that accepts space-separated version strings and an optional 'DRIVER' flag

These will all be made public to the end users.

Will be used in the following 3 places:
1. CMake INSTALL_<RUNTIME> flag will invoke the script if it's available for 'RUNTIME'
2. Our Dockerfile will make use of the degirum install-runtime flag AND the DRIVER flag
(degirum install-runtime <runtime> DRIVER) to install the runtime AND driver.
3. For use by end users by using 'degirum install-runtime <runtime>'
(degirum install-runtime <runtime>) will call the script with only the latest version of the runtime.

Note: for end users, we do not make the 'DRIVER' flag shown in public-facing documentation / command help usage.
It will only be used by the Dockerfile.



The template directory contains 2 template scripts, all that a runtime needs to do is to copy the template and implement the install_runtime() and install_driver() functions.

```