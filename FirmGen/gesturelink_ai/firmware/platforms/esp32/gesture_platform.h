/* ESP-IDF adapter initialization for the configured LED and UART console. */
#ifndef GESTURE_PLATFORM_H
#define GESTURE_PLATFORM_H

#include <stdbool.h>

#include "gesture_io.h"

/**
 * @brief Initializes the LED output and places it in logical OFF state.
 *
 * @return true when the configured GPIO is ready and OFF; otherwise false.
 */
bool gesture_platform_init(void);

/**
 * @brief Returns the LED and UART callback table used by the command service.
 *
 * @return Borrowed callback table valid for the lifetime of the firmware.
 */
const gesture_io_t *gesture_platform_io(void);

#endif /* GESTURE_PLATFORM_H */
