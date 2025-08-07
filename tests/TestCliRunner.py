from click.testing import Result
from typer import Typer
from typer.testing import CliRunner


from typing import Optional, Sequence, Union


class TestCliRunner(CliRunner):
    def __init__(self, so_mag_app: Typer, caplog):
        self.so_mag_app = so_mag_app
        self.caplog = caplog
        super().__init__(mix_stderr=False)

    def invoke_and_verify(  # type: ignore
        self,
        args: Optional[Union[str, Sequence[str]]] = None,
        expected_exit_code=0,
    ) -> Result:
        if args is str:
            print(f"Invoking so-mag {args}")
        else:
            print(f"Invoking so-mag {' '.join(args)}")
        catch_exceptions = expected_exit_code != 0
        result = super().invoke(
            self.so_mag_app,
            args=args,
            catch_exceptions=catch_exceptions,
        )
        self.result = result
        print(result.output)
        if result.exception and expected_exit_code == 0:
            raise result.exception

        assert result.exit_code == expected_exit_code
        return result

    def verify_output(self, expected_output: str):
        assert (
            expected_output in self.caplog.text or expected_output in self.result.output
        )
        return True
