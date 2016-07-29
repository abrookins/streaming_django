# How does Django's `StreamingHttpResponse` work, exactly?

This repository exists to explain just what goes on when you use Django's
`StreamingHttpResponse`.

I will discuss what happens in your Django application, what happens at the
Python Web Server Gateway Interface (WSGI) layer, and look at some examples.

## How to use this repository

Just read this document (README.md).

If you want to experiment with running `curl` requests against a streaming vs.
non-streaming Django view, follow the next section, "Running the
`streaming_django` project," to install the included example Django project.

### Running the `streaming_django` project

First, [install docker](https://www.docker.com/), including `docker-compose`,
and then get a machine started.

When you have a Docker machine running, do the following:

	$ git clone git@github.com:abrookins/streaming_django.git
	$ cd streaming_django
	$ docker-compose build
	$ docker-compose up

Now you're ready to make a request:

	$ curl -vv --raw "http://192.168.99.100/download_csv_streaming"

Or:

	$ curl -vv --raw "http://192.168.99.100/download_csv" 

**Pro tip**: The `--raw` flag is important if you want to see that a response
is actually streaming. Without it, you won't see much difference between a
streaming and non-streaming response.

## So, what even is a `StreamingHttpResponse`?

Most Django responses use `HttpResponse`. At a high level, this means that the
body of the response is built in memory and sent to the HTTP client in a single
piece.

Here's a short example of using `HttpResponse`:

```python
    def my_view(request):
        message = 'Hello, there!'
        response =  HttpResponse(message)
        response['Content-Length'] = len(message)

        return response
```

A `StreamingHttpResponse`, on the other hand, is a response whose body is sent
to the client in multiple pieces, or "chunks."

Here's a short example of using `StreamingHttpResponse`:

```python
    def hello():
        yield 'Hello,'
        yield 'there!'

    def my_view(request):
        # NOTE: No Content-Length header!
        return StreamingHttpResponse(hello)
```

You can read more about how to use these two classes in [Django's
documentation](https://docs.djangoproject.com/en/1.9/ref/request-response/).
The interesting part is what happens next -- *after* you return the response.

## When would you use a `StreamingHttpResponse`?

But before we talk about what happens *after* you return the response, let us
digress for a moment: why would you even use a `StreamingHttpResponse`?

One of the best use cases for streaming responses is to send large files, e.g.
a large CSV file.

With an `HttpResponse`, you would typically load the entire file into memory
(produced dynamically or not) and then send it to the client. For a large file,
this costs memory on the server and "time to first byte" (TTFB) sent to the
client.

With a `StreamingHttpResponse`, you can load parts of the file into memory, or
produce parts of the file dynamically, and begin sending these parts to the
client immediately. **Crucially,** there is no need to load the entire file
into memory.

## A quick note about WSGI

Now we're approaching the part of our journey that lies just beyond most Django
developers' everyday experience of working with Django's response classes.

Yes, we're about to discuss the [Python Web Server Gateway Interface (WSGI)
specification](https://www.python.org/dev/peps/pep-3333/).

So, a quick note if you aren't familiar with WSGI. WSGI is a specification that
proposes rules that web frameworks and web servers should follow in order that
you, the framework user, can swap out one WSGI server (like uWSGI) for another
(Gunicorn) and expect your Python web application to continue to function.

## Django and WSGI

And now, back to our journey into deeper knowledge!

So, what happens after your Django view returns a `StreamingHttpResponse`? In
most Python web applications, the response is passed off to a WSGI server like
uWSGI or Gunicorn (AKA, Green Unicorn).

As with `HttpResponse`, Django ensures that `StreamingHttpResponse` conforms to
the WSGI spec, which states this:

> When called by the server, the application object must return an iterable
> yielding zero or more bytestrings. This can be accomplished in a variety of
> ways, such as by returning a list of bytestrings, or by the application being a
> generator function that yields bytestrings, or by the application being a class
> whose instances are iterable.

Here's how `StreamingHttpResponse` satisfies these requirements ([full
source](https://docs.djangoproject.com/en/1.9/_modules/django/http/response/#StreamingHttpResponse)):

```python
    @property
    def streaming_content(self):
        return map(self.make_bytes, self._iterator)
# ...

    def __iter__(self):
        return self.streaming_content
```

You give the class a generator and it coerces the values that it produces into
bytestrings.

Compare that with the approach in `HttpResponse` ([full source](https://docs.djangoproject.com/en/1.9/_modules/django/http/response/#HttpResponse)):

```python
    @content.setter
    def content(self, value):
        # ...
        self._container = [value]

    def __iter__(self):
        return iter(self._container)
```

Ah ha! An iterator with a single item. Very interesting. Now, let's take a look
at what a WSGI server does with these two different responses.

## The WSGI server

Gunicorn's synchronous worker offers a good example of what happens after
Django returns a response object. The code is [relatively
short](https://github.com/benoitc/gunicorn/blob/39f62ac66beaf83ceccefbfabd5e3af7735d2aff/gunicorn/workers/sync.py#L176-L183)
-- here's the important part (for our purposes):

```python
respiter = self.wsgi(environ, resp.start_response)
try:
    if isinstance(respiter, environ['wsgi.file_wrapper']):
        resp.write_file(respiter)
    else:
        for item in respiter:
            resp.write(item)
    resp.close()
```

Whether your response is streaming or not, Gunicorn iterates over it and writes
each string the response yields. If that's the case, then what makes your
streaming response actually "stream"?

First, some conditions must be true:

* The client must be speaking HTTP/1.1 or newer
* The request method wasn't a HEAD
* The response does not include a Content-Length header
* The response status wasn't 204 or 304

If these conditions are true, then Gunicorn will add a `Transfer-Encoding:
chunked` header to the response, signaling to the client that the response will
stream in chunks.

In fact, Gunicorn will respond with `Transfer-Encoding: chunked` even if you
used an `HttpResponse`, if those conditions are true!

To really stream a response, that is, to send it to the client in pieces, the
conditions must be true, *and* your response needs to be an iterable with
multiple items.

### What does the client get?

If the streaming response worked, the client should get an HTTP 1.1 response
with the `Transfer-Encoding: chunked` header, and instead of a single piece of
content with a `Content-Length`, the client should see each bytestring that
your generator/iterator yielded, sent with the length of that chunk.

Here is an example that uses the code in this repository:

```
(streaming_django) ❯ curl -vv --raw "http://192.168.99.100/download_csv_streaming"
*   Trying 192.168.99.100...
* Connected to 192.168.99.100 (192.168.99.100) port 80 (#0)
> GET /download_csv_streaming HTTP/1.1
> Host: 192.168.99.100
> User-Agent: curl/7.43.0
> Accept: */*
>
< HTTP/1.1 200 OK
< Server: nginx/1.11.1
< Date: Fri, 29 Jul 2016 14:27:58 GMT
< Content-Type: text/csv
< Transfer-Encoding: chunked
< Connection: keep-alive
< X-Frame-Options: SAMEORIGIN
< Content-Disposition: attachment; filename=big.csv
<
f
One,Two,Three

f
Hello,world,1

...

10
Hello,world,99

0

* Connection #0 to host 192.168.99.100 left intact
```

So there you have it. We journeyed from considering when to use
`StreamingHttpResponse` over `HttpResponse`, to an example of using the class
in your Django project, then into the dungeons of WSGI and WSGI servers, and
finally to the client's experience. And we managed to stream a response -- go
us!
