import { extendTheme, type ThemeConfig } from '@chakra-ui/react'

const config: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: true,
}

const theme = extendTheme({
  config,
  colors: {
    brand: {
      50: '#eef4ff',
      100: '#d9e6ff',
      200: '#b6ceff',
      300: '#8eaeff',
      400: '#5f85ff',
      500: '#3a63f5',
      600: '#2f4cd1',
      700: '#263ca9',
      800: '#1e2f82',
      900: '#15225d',
    },
    accent: {
      50: '#fff6e5',
      100: '#ffe7b8',
      200: '#ffd280',
      300: '#ffba47',
      400: '#f6a213',
      500: '#d68604',
      600: '#aa6900',
      700: '#7e4c00',
      800: '#533100',
      900: '#291800',
    },
  },
  fonts: {
    heading: 'var(--font-jakarta), "Plus Jakarta Sans", system-ui, -apple-system, sans-serif',
    body: 'var(--font-jakarta), "Plus Jakarta Sans", system-ui, -apple-system, sans-serif',
  },
  styles: {
    global: (props: any) => ({
      body: {
        bg: props.colorMode === 'dark' 
          ? 'linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #334155 100%)'
          : 'linear-gradient(135deg, #f6f8ff 0%, #eef2ff 40%, #f7fafc 100%)',
        color: props.colorMode === 'dark' ? '#f1f5f9' : '#0f172a',
      },
      '::selection': {
        background: 'brand.200',
        color: props.colorMode === 'dark' ? '#0f172a' : '#0f172a',
      },
    }),
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: 700,
        borderRadius: 'full',
        letterSpacing: '0.2px',
      },
      sizes: {
        xl: {
          h: 14,
          px: 8,
          fontSize: 'lg',
        },
      },
      variants: {
        solid: {
          bg: 'brand.600',
          color: 'white',
          boxShadow: '0 15px 40px rgba(47, 76, 209, 0.28)',
          _hover: { bg: 'brand.500', transform: 'translateY(-1px)' },
          _active: { bg: 'brand.700' },
          _dark: {
            bg: 'brand.500',
            boxShadow: '0 15px 40px rgba(95, 133, 255, 0.35)',
            _hover: { bg: 'brand.400' },
            _active: { bg: 'brand.600' },
          },
        },
        outline: {
          borderColor: 'brand.200',
          color: 'brand.700',
          _hover: { bg: 'brand.50', borderColor: 'brand.300' },
        },
        ghost: {
          color: 'brand.700',
          _hover: { bg: 'brand.50' },
        },
      },
    },
    Card: {
      baseStyle: {
        rounded: '2xl',
        borderWidth: '1px',
        borderColor: 'blackAlpha.50',
        shadow: 'md',
        _dark: {
          bg: 'whiteAlpha.50',
          borderColor: 'whiteAlpha.100',
          shadow: 'dark-lg',
        },
      },
    },
    Tag: {
      baseStyle: {
        borderRadius: 'full',
        fontWeight: 600,
        textTransform: 'none',
      },
    },
    Input: {
      variants: {
        filled: {
          field: {
            borderRadius: 'xl',
            bg: 'white',
            borderWidth: '1px',
            borderColor: 'blackAlpha.100',
            _hover: { borderColor: 'brand.200' },
            _focus: {
              borderColor: 'brand.400',
              boxShadow: '0 0 0 1px rgba(58, 99, 245, 0.35)',
            },
          },
        },
      },
      defaultProps: {
        variant: 'filled',
        size: 'lg',
      },
    },
  },
})

export { config as themeConfig }
export default theme
