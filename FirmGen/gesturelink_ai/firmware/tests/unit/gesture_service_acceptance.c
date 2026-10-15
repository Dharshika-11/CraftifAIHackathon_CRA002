/* Host acceptance tests for the hardware-independent GestureLink command policy. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include "app_config.h"
#include "board.h"
#include "gesture_io.h"
#include "gesture_service.h"

#define TEST_INPUT_CAPACITY 4U
#define TEST_COMMAND_CAPACITY 48U

typedef struct
{
    bool led_is_on;
    bool initialized;
    bool led_state_at_read;
    bool report_accepted[TEST_INPUT_CAPACITY];
    unsigned int report_count;
    char reported_commands[TEST_INPUT_CAPACITY][TEST_COMMAND_CAPACITY];
} test_fixture_t;

typedef struct
{
    const char *text;
    size_t length;
} test_line_t;

static test_fixture_t fixture;
static test_line_t input_lines[TEST_INPUT_CAPACITY];
static size_t input_count;
static size_t input_index;
static bool overflow_line_pending;

/* Track reported results in the same accepted/rejected form used by the ESP-IDF adapter. */
static void test_initialize_lines(void)
{
    input_lines[0] = (test_line_t){ .text = "LIGHT_ON", .length = sizeof("LIGHT_ON") - 1U };
    input_lines[1] = (test_line_t){ .text = "LIGHT_OFF", .length = sizeof("LIGHT_OFF") - 1U };
    input_lines[2] = (test_line_t){ .text = "LIGHT_ON extra", .length = sizeof("LIGHT_ON extra") - 1U };
    input_lines[3] = (test_line_t){ .text = "UNSUPPORTED", .length = sizeof("UNSUPPORTED") - 1U };
    input_count = TEST_INPUT_CAPACITY;
}

static bool test_initialize_led(void)
{
    fixture.led_is_on = false;
    fixture.initialized = true;
    return true;
}

static bool test_set_led(bool is_on)
{
    fixture.led_is_on = is_on;
    return true;
}

static bool test_read_line(char *buffer, size_t capacity, size_t *length)
{
    size_t copy_length;

    if ((buffer == NULL) || (length == NULL) || (capacity < 2U))
    {
        return false;
    }

    if (overflow_line_pending)
    {
        overflow_line_pending = false;
        memset(buffer, 'X', capacity - 1U);
        buffer[capacity - 1U] = '\0';
        *length = capacity;
        return true;
    }

    if (input_index >= input_count)
    {
        return false;
    }

    fixture.led_state_at_read = fixture.led_is_on;
    copy_length = input_lines[input_index].length;
    if (copy_length >= capacity)
    {
        copy_length = capacity - 1U;
    }

    memcpy(buffer, input_lines[input_index].text, copy_length);
    buffer[copy_length] = '\0';
    *length = input_lines[input_index].length;
    input_index++;
    return true;
}

static void test_report_command(bool accepted, const char *command)
{
    size_t report_index = fixture.report_count;
    const char *result_prefix = accepted ? "Command accepted: " : "Command rejected: ";

    assert(report_index < TEST_INPUT_CAPACITY);
    fixture.report_accepted[report_index] = accepted;
    (void)snprintf(fixture.reported_commands[report_index], TEST_COMMAND_CAPACITY,
                   "%s%s", result_prefix, command);
    fixture.report_count++;
}

static const gesture_io_t test_io = {
    .initialize_led = test_initialize_led,
    .set_led = test_set_led,
    .read_line = test_read_line,
    .report_command = test_report_command
};

static void reset_fixture(void)
{
    memset(&fixture, 0, sizeof(fixture));
    input_count = 0U;
    input_index = 0U;
    overflow_line_pending = false;
}

static void test_board_led_configuration(void)
{
    assert(APP_LED_GPIO == 38U);
    assert(BOARD_LED_GPIO == 38U);
    assert(BOARD_LED_ACTIVE_LEVEL == 1);
    assert(board_led_level(true) == 1U);
    assert(board_led_level(false) == 0U);
}

static void test_startup_initializes_led_off(void)
{
    reset_fixture();
    assert(test_io.initialize_led());
    assert(fixture.initialized);
    assert(!fixture.led_is_on);
}

static void test_light_on_turns_led_on(void)
{
    reset_fixture();
    assert(test_io.initialize_led());
    assert(gesture_service_execute("LIGHT_ON", sizeof("LIGHT_ON") - 1U, &test_io) ==
           GESTURE_COMMAND_ACCEPTED);
    assert(fixture.led_is_on);
}

static void test_light_off_turns_led_off(void)
{
    reset_fixture();
    assert(test_io.initialize_led());
    assert(test_io.set_led(true));
    assert(gesture_service_execute("LIGHT_OFF", sizeof("LIGHT_OFF") - 1U, &test_io) ==
           GESTURE_COMMAND_ACCEPTED);
    assert(!fixture.led_is_on);
}

static void test_invalid_commands_never_turn_led_on(void)
{
    reset_fixture();
    assert(test_io.initialize_led());
    assert(!fixture.led_is_on);
    assert(gesture_service_execute("unsupported", sizeof("unsupported") - 1U, &test_io) ==
           GESTURE_COMMAND_REJECTED);
    assert(!fixture.led_is_on);
    assert(gesture_service_execute("LIGHT_ON extra", sizeof("LIGHT_ON extra") - 1U, &test_io) ==
           GESTURE_COMMAND_REJECTED);
    assert(!fixture.led_is_on);

    assert(test_io.set_led(true));
    assert(gesture_service_execute("light_on", sizeof("light_on") - 1U, &test_io) ==
           GESTURE_COMMAND_REJECTED);
    assert(fixture.led_is_on);
}

static void test_crlf_is_accepted(void)
{
    reset_fixture();
    assert(gesture_service_execute("LIGHT_ON\r\n", sizeof("LIGHT_ON\r\n") - 1U, &test_io) ==
           GESTURE_COMMAND_ACCEPTED);
    assert(fixture.led_is_on);
}

static void test_fragmented_line_assembly(void)
{
    char assembled[TEST_COMMAND_CAPACITY] = { 0 };
    const char fragment_a[] = "LIGHT_";
    const char fragment_b[] = "ON";

    memcpy(assembled, fragment_a, sizeof(fragment_a) - 1U);
    memcpy(&assembled[sizeof(fragment_a) - 1U], fragment_b, sizeof(fragment_b));
    assert(gesture_service_execute(assembled, sizeof("LIGHT_ON") - 1U, &test_io) ==
           GESTURE_COMMAND_ACCEPTED);
    assert(fixture.led_is_on);
}

static void test_overlong_input_is_rejected(void)
{
    char overlong_command[APP_COMMAND_BUFFER_SIZE + 1U];

    memset(overlong_command, 'X', sizeof(overlong_command));
    assert(gesture_service_execute(overlong_command, APP_COMMAND_LINE_CAPACITY + 1U, &test_io) ==
           GESTURE_COMMAND_REJECTED);
}

static void test_service_processes_commands_and_reports_results(void)
{
    reset_fixture();
    test_initialize_lines();
    assert(!gesture_service_run(&test_io));
    assert(fixture.initialized);
    assert(fixture.report_count == TEST_INPUT_CAPACITY);
    assert(fixture.report_accepted[0]);
    assert(strcmp(fixture.reported_commands[0], "Command accepted: LIGHT_ON") == 0);
    assert(fixture.led_state_at_read == false);
    assert(fixture.report_accepted[1]);
    assert(strcmp(fixture.reported_commands[1], "Command accepted: LIGHT_OFF") == 0);
    assert(!fixture.report_accepted[2]);
    assert(strcmp(fixture.reported_commands[2], "Command rejected: LIGHT_ON extra") == 0);
    assert(!fixture.report_accepted[3]);
    assert(strcmp(fixture.reported_commands[3], "Command rejected: UNSUPPORTED") == 0);
    assert(!fixture.led_is_on);
}

static void test_service_reports_overlong_line_as_invalid(void)
{
    reset_fixture();
    overflow_line_pending = true;
    assert(!gesture_service_run(&test_io));
    assert(fixture.initialized);
    assert(fixture.report_count == 1U);
    assert(!fixture.report_accepted[0]);
    assert(strcmp(fixture.reported_commands[0], "Command rejected: INVALID") == 0);
}

typedef void (*test_function_t)(void);

typedef struct
{
    const char *name;
    test_function_t function;
} named_test_t;

int main(void)
{
    static const named_test_t tests[] = {
        { "board LED configuration", test_board_led_configuration },
        { "startup initializes LED OFF", test_startup_initializes_led_off },
        { "LIGHT_ON turns LED on", test_light_on_turns_led_on },
        { "LIGHT_OFF turns LED off", test_light_off_turns_led_off },
        { "invalid commands do not turn LED on", test_invalid_commands_never_turn_led_on },
        { "CRLF command line", test_crlf_is_accepted },
        { "fragmented command line", test_fragmented_line_assembly },
        { "overlong command rejected", test_overlong_input_is_rejected },
        { "command service and UART result reporting", test_service_processes_commands_and_reports_results },
        { "overlong service line logged as invalid", test_service_reports_overlong_line_as_invalid }
    };
    size_t test_index;
    size_t test_count = sizeof(tests) / sizeof(tests[0]);

    for (test_index = 0U; test_index < test_count; test_index++)
    {
        tests[test_index].function();
        (void)printf("PASS: %s\n", tests[test_index].name);
    }

    (void)printf("All %u acceptance tests passed.\n", (unsigned int)test_count);
    return 0;
}
