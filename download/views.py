import csv
from io import StringIO

from django.http import StreamingHttpResponse


def big_csv(num_rows):
    for row in range(num_rows):
        output = StringIO()
        writer = csv.writer(output)

        if row == 0:
            writer.writerow(['One', 'Two', 'Three'])
        else:
            writer.writerow(['Hello', 'world', row])

        output.seek(0)
        yield output.read()


def download_csv(request):
    """Return a CSV file.

    This view responds with a chunked HTTP response, generating
    each row of the response as it's created.
    """
    response = StreamingHttpResponse(big_csv(1000), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=big.csv'

    return response
