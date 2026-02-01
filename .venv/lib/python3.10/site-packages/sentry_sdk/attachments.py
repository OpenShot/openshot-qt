import os
import mimetypes

from sentry_sdk.envelope import Item, PayloadRef

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Union, Callable


class Attachment:
    """Additional files/data to send along with an event.

    This class stores attachments that can be sent along with an event. Attachments are files or other data, e.g.
    config or log files, that are relevant to an event. Attachments are set on the ``Scope``, and are sent along with
    all non-transaction events (or all events including transactions if ``add_to_transactions`` is ``True``) that are
    captured within the ``Scope``.

    To add an attachment to a ``Scope``, use :py:meth:`sentry_sdk.Scope.add_attachment`. The parameters for
    ``add_attachment`` are the same as the parameters for this class's constructor.

    :param bytes: Raw bytes of the attachment, or a function that returns the raw bytes. Must be provided unless
                  ``path`` is provided.
    :param filename: The filename of the attachment. Must be provided unless ``path`` is provided.
    :param path: Path to a file to attach. Must be provided unless ``bytes`` is provided.
    :param content_type: The content type of the attachment. If not provided, it will be guessed from the ``filename``
                         parameter, if available, or the ``path`` parameter if ``filename`` is ``None``.
    :param add_to_transactions: Whether to add this attachment to transactions. Defaults to ``False``.
    """

    def __init__(
        self,
        bytes: "Union[None, bytes, Callable[[], bytes]]" = None,
        filename: "Optional[str]" = None,
        path: "Optional[str]" = None,
        content_type: "Optional[str]" = None,
        add_to_transactions: bool = False,
    ) -> None:
        if bytes is None and path is None:
            raise TypeError("path or raw bytes required for attachment")
        if filename is None and path is not None:
            filename = os.path.basename(path)
        if filename is None:
            raise TypeError("filename is required for attachment")
        if content_type is None:
            content_type = mimetypes.guess_type(filename)[0]
        self.bytes = bytes
        self.filename = filename
        self.path = path
        self.content_type = content_type
        self.add_to_transactions = add_to_transactions

    def to_envelope_item(self) -> "Item":
        """Returns an envelope item for this attachment."""
        payload: "Union[None, PayloadRef, bytes]" = None
        if self.bytes is not None:
            if callable(self.bytes):
                payload = self.bytes()
            else:
                payload = self.bytes
        else:
            payload = PayloadRef(path=self.path)
        return Item(
            payload=payload,
            type="attachment",
            content_type=self.content_type,
            filename=self.filename,
        )

    def __repr__(self) -> str:
        return "<Attachment %r>" % (self.filename,)
