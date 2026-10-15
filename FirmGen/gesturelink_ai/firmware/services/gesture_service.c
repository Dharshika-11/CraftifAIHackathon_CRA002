/* Exact command validation and LED state changes without vendor dependencies. */
#include "gesture_service.h"

#include <string.h>

#include "app_config.h"

static const char command_light_on[] = "LIGHT_ON";
static const char command_light_off[] = "LIGHT_OFF";

/* Strip only transport line terminators; command content remains exact and case-sensitive. */
static size_t gesture_service_trim_line_endings(const char *command, size_t length)
{
    while ((length > 0U) && ((command[length - 1U] == '\r') || (command[length - 1U] == '\n')))
    {
        length--;
    }

    return length;
}

gesture_command_result_t gesture_service_execute(const char *command, size_t length,
                                                  const gesture_io_t *io)
{
    size_t command_length;
    bool desired_state;
    bool is_valid_command;

    if ((command == NULL) || (io == NULL) || (io->set_led == NULL) ||
        (length > APP_COMMAND_LINE_CAPACITY))
    {
        return GESTURE_COMMAND_REJECTED;
    }

    command_length = gesture_service_trim_line_endings(command, length);
    is_valid_command = false;
    desired_state = false;

    if ((command_length == (sizeof(command_light_on) - 1U)) &&
        (memcmp(command, command_light_on, command_length) == 0))
    {
        is_valid_command = true;
        desired_state = true;
    }
    else if ((command_length == (sizeof(command_light_off) - 1U)) &&
             (memcmp(command, command_light_off, command_length) == 0))
    {
        is_valid_command = true;
        desired_state = false;
    }
    else
    {
        /* Invalid strings are intentionally side-effect free. */
    }

    if (!is_valid_command || !io->set_led(desired_state))
    {
        return GESTURE_COMMAND_REJECTED;
    }

    return GESTURE_COMMAND_ACCEPTED;
}

/* The same service policy runs on the device and against host-provided callbacks. */
bool gesture_service_run(const gesture_io_t *io)
{
    char command_buffer[APP_COMMAND_BUFFER_SIZE];
    size_t command_length;

    if ((io == NULL) || (io->initialize_led == NULL) || (io->set_led == NULL) ||
        (io->read_line == NULL) || (io->report_command == NULL) || !io->initialize_led())
    {
        return false;
    }

    for (;;)
    {
        bool is_overlong;

        if (!io->read_line(command_buffer, sizeof(command_buffer), &command_length))
        {
            return false;
        }

        is_overlong = command_length > APP_COMMAND_LINE_CAPACITY;
        if (is_overlong)
        {
            io->report_command(false, "INVALID");
        }
        else
        {
            gesture_command_result_t result = gesture_service_execute(command_buffer,
                                                                      command_length, io);
            io->report_command((result == GESTURE_COMMAND_ACCEPTED), command_buffer);
        }
    }
}
