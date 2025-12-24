'use client';

import { ReactNode } from 'react';
import { Box, Flex, useColorModeValue, useBreakpointValue } from '@chakra-ui/react';
import { SessionSidebar } from './SessionSidebar';
import { UsageBar } from './UsageBar';

interface WorkspaceLayoutProps {
  children: ReactNode;
}

export function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const isMobile = useBreakpointValue({ base: true, lg: false });

  const sidebarBg = useColorModeValue('gray.50', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  if (isMobile) {
    return (
      <Flex direction="column" h="100vh" overflow="hidden">
        <Flex flex="1" overflow="hidden">
          <Box flex="1" overflow="hidden">
            {children}
          </Box>
        </Flex>
        <UsageBar />
      </Flex>
    );
  }

  return (
    <Flex direction="column" h="100vh" overflow="hidden">
      <Flex flex="1" overflow="hidden">
        <Box
          w="340px"
          minW="340px"
          maxW="340px"
          bg={sidebarBg}
          borderRightWidth="1px"
          borderColor={borderColor}
          overflow="hidden"
        >
          <SessionSidebar />
        </Box>

        <Box flex="1" overflow="hidden">
          {children}
        </Box>
      </Flex>

      <UsageBar />
    </Flex>
  );
}
