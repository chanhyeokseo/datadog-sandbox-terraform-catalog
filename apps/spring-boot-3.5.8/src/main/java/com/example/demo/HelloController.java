package com.example.demo;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.Collections;

import io.opentracing.Scope;
import io.opentracing.Span;
import io.opentracing.Tracer;
import io.opentracing.log.Fields;
import io.opentracing.tag.Tags;
import io.opentracing.util.GlobalTracer;
import datadog.trace.api.DDTags;
import datadog.trace.api.Trace;

@RestController
public class HelloController {

	/**
	 * Basic endpoint - generates a trace with no custom instrumentation
	 */
	@GetMapping("/")
	public String index() {
		return "Hello World!";
	}

	/**
	 * Add custom tags to the current span
	 */
	@GetMapping("/add-tag")
	public String addTag() {
		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			LocalDate today = LocalDate.now();
			span.setTag("date", today.toString());
			span.setTag("custom.tag", "example-value");
		}
		return "Added tags to span";
	}

	/**
	 * Set an error on the current span
	 */
	@GetMapping("/set-error")
	public String setError() {
		final Span span = GlobalTracer.get().activeSpan();
		if (span != null) {
			try {
				int[] smallArray = {1};
				System.out.println(smallArray[1]); // ArrayIndexOutOfBoundsException
			} catch (Exception ex) {
				span.setTag(Tags.ERROR, true);
				span.log(Collections.singletonMap(Fields.ERROR_OBJECT, ex));
			}
		}
		return "Error set on span";
	}

	/**
	 * Create a span using @Trace annotation
	 */
	@GetMapping("/trace-annotation")
	public String traceAnnotation() {
		doSomeWork();
		return "Created span with @Trace annotation";
	}

	@Trace(operationName = "manual.span", resourceName = "doSomeWork")
	private void doSomeWork() {
		try {
			Thread.sleep(500);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
		}
	}

	/**
	 * Manually create a span
	 */
	@GetMapping("/manual-span")
	public String manualSpan() {
		Tracer tracer = GlobalTracer.get();
		Span span = tracer.buildSpan("manual.span")
				.withTag(DDTags.SERVICE_NAME, "manual-service")
				.withTag(DDTags.RESOURCE_NAME, "ManualOperation")
				.start();

		try (Scope scope = tracer.activateSpan(span)) {
			span.setTag("state", "crafted");
			Thread.sleep(300);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
		} finally {
			span.finish();
		}

		return "Manually created span";
	}

	/**
	 * Simulate slow endpoint for latency testing
	 */
	@GetMapping("/slow")
	public String slow() {
		try {
			Thread.sleep(2000);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
		}
		return "Slow response after 2 seconds";
	}
}

