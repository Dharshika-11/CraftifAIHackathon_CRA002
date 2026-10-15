/* Public interface for exact LED command validation and state changes. */
#ifndef GESTURE_SERVICE_H
#define GESTURE_SERVICE_H

#include <stdbool.h>
#include <stddef.h>

#include "gesture_io.h"

typedef enum
{
    GESTURE_COMMAND_REJECTED = 0,
    GESTURE_COMMAND_ACCEPTED = 1
} gesture_command_result_t;

/**
 * @brief Applies one complete line-oriented LED command.
 *
 * Accepts only the exact ASCII strings LIGHT_ON and LIGHT_OFF. Trailing CR or
 * LF bytes are ignored so console line endings are accepted. All other input
 * is rejected without changing the LED state. The supplied length must not
 * exceed the configured maximum command-line payload.
 *
 * @param[in] command Borrowed command bytes; must be non-NULL and contain at least length readable bytes.
 * @param[in] length Number of bytes in command, excluding any terminator.
 * @param[in,out] io Borrowed LED output callback; must provide set_led.
 *
 * @return GESTURE_COMMAND_ACCEPTED if a valid command successfully updates the LED.
 * @return GESTURE_COMMAND_REJECTED for malformed input or a failed LED update.
 *
 * @pre The platform has initialized LED GPIO to logical OFF.
 * @post Invalid input leaves the previously requested output unchanged.
 */
gesture_command_result_t gesture_service_execute(const char *command, size_t length,
                                                  const gesture_io_t *io);

/**
 * @brief Initializes the LED, then continuously handles complete input lines.
 *
 * @param[in] io Borrowed I/O callback table with initialize_led, set_led, and read_line.
 *
 * @return true when initialization succeeds and command processing begins.
 * @return false if the callback table is invalid or LED initialization fails.
 *
 * @pre The platform console is initialized before this function is called, and report_command is non-NULL.
 * @post Successful calls continuously read commands, update LED state, and report each result.
 */
bool gesture_service_run(const gesture_io_t *io);

#endif /* GESTURE_SERVICE_H */
