import csv
from io import StringIO

from django.http import StreamingHttpResponse, HttpResponse


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

    This view reponds with the entire content of the CSV file in a single piece.
    """
    csv_file = ''.join(big_csv(100))
    response = HttpResponse(csv_file, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=big.csv'
    response['Content-Length'] = len(csv_file)

    return response


def download_csv_streaming(request):
    """Return a CSV file.

    This view responds with a generator that yields each row of the response as
    it's created.
    """
    response = StreamingHttpResponse(big_csv(100), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=big.csv'

    return response
