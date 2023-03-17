from abc import ABC, abstractmethod
import logging
import subprocess as sp
import re

logger = logging.getLogger(__name__)

class DoctorRoutine(ABC):

    @staticmethod
    @abstractmethod
    def diagnose() -> bool:
        """This method should check if diagnosed component is set up correctly."""
        pass

    @staticmethod
    @abstractmethod
    def try_to_fix(self):
        """This method should try to fix the problem or at least show recommendation how user can solve the problem"""
        pass


class DoctorCheckDocker(DoctorRoutine):
    """This DoctorRoutine checks if Docker is available"""

    @staticmethod
    def diagnose() -> bool:
        docker_is_available = False
        try:
            docker_version = sp.run(["docker", "--version"], capture_output=True)
            docker_version = re.findall('Docker version (.*),.*', docker_version.stdout.decode("utf-8"))
            docker_is_available = True
        except FileNotFoundError:
            pass  # Command not found, so docker is not visible for python environment
        return docker_is_available

    @staticmethod
    def try_to_fix():
        how_to_str = "Docker is not available, please install Docker (using `brew install docker` command or " \
                     "following instruction here: https://docs.docker.com/get-docker/"
        print(how_to_str)


class PoetryCheckDocker(DoctorRoutine):
    """This DoctorRoutine checks if Poetry is available"""

    @staticmethod
    def diagnose() -> bool:
        poetry_is_available = False
        try:
            poetry_version = sp.run(["poetryy", "--version"], capture_output=True)
            poetry_version = re.findall('Poetry \(version (.*)\).*', poetry_version.stdout.decode("utf-8"))
            poetry_is_available = True
        except FileNotFoundError:
            pass  # Command not found, so docker is not visible for python environment
        return poetry_is_available

    @staticmethod
    def try_to_fix():
        how_to_str = "Please install poetry (you can use `pipx install poetry` or follow " \
                     " instruction here: https://python-poetry.org/docs/#installing-with-pipx"
        print(how_to_str)
        print("Or you can install it now with pipx. Do you want to do it now [Y/N] (No is default) ")
        input_from_user = input()
        if input_from_user == 'Y':
            print("...working hard...\nDone!")


class Doctor:
    doctor_procedure = {
        DoctorCheckDocker,
        PoetryCheckDocker,
    }
    @staticmethod
    def hello_world():
        logger.debug("I'm really chatty")
        logger.info("Hello, I'm the doctor")
        logger.warning("You ought to be careful")
        logger.error("This is very wrong")
        struggle_list = Doctor.run_diagnose()
        Doctor.try_to_fix(struggle_list)

    @staticmethod
    def run_diagnose() -> list[DoctorRoutine]:
        struggle_list = []
        for procedure in Doctor.doctor_procedure:
            diagnose_ok = procedure.diagnose()
            logger_t = logger.warning if diagnose_ok else logger.error
            logger_t(f"{procedure.__doc__} -> Status: {diagnose_ok}")
            if not diagnose_ok:
                struggle_list.append(procedure)
        return struggle_list

    @staticmethod
    def try_to_fix(struggle_list: list[DoctorRoutine]):
        for procedure in struggle_list:
            procedure.try_to_fix()
