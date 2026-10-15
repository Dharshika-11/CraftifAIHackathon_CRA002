/* Command I/O interface shared by application logic and platform adapters. */
#ifndef GESTURE_IO_H
#define GESTURE_IO_H

#include <stdbool.h>
#include <stddef.h>

/** Callback functions providing physical LED and UART line operations. */
typedef struct
{
    bool (*initialize_led)(void);
    bool (*set_led)(bool is_on);
    bool (*read_line)(char *buffer, size_t capacity, size_t *length);
    void (*report_command)(bool accepted, const char *command);
} gesture_io_t;

/**
 * @brief Retrieves the active platform implementation of the command I/O contract.
 *
 * @return Borrowed callback table valid for the firmware lifetime, or NULL if unavailable.
 */
const gesture_io_t *gesture_io_get(void);

#endif /* GESTURE_IO_H */
