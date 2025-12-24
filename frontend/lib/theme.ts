import { extendTheme, type ThemeConfig } from '@chakra-ui/react'

const config: ThemeConfig = {
  initialColorMode: 'system',
  useSystemColorMode: true,
}

const theme = extendTheme({
  config,
  colors: {
    brand: {
      50: '#e6f4fb',
      100: '#b3dff4',
      200: '#80caed',
      300: '#4db5e6',
      400: '#1aa0df',
      500: '#007CBA',
      600: '#006395',
      700: '#004a70',
      800: '#00324a',
      900: '#001925',
    },
    fdaNavy: {
      50: '#e8e9f0',
      100: '#b9bdd3',
      200: '#8a91b6',
      300: '#5b6599',
      400: '#3e4880',
      500: '#222C67',
      600: '#1b2352',
      700: '#141a3e',
      800: '#0d1129',
      900: '#060815',
    },
    fdaGold: {
      50: '#fef9e6',
      100: '#fcecb3',
      200: '#f9df80',
      300: '#f6d24d',
      400: '#f3c51a',
      500: '#E5B611',
      600: '#b7920e',
      700: '#896d0a',
      800: '#5c4907',
      900: '#2e2403',
    },
    fdaRed: {
      50: '#fce6eb',
      100: '#f5b3c2',
      200: '#ee8099',
      300: '#e74d70',
      400: '#e01a47',
      500: '#D60036',
      600: '#ab002b',
      700: '#800020',
      800: '#560016',
      900: '#2b000b',
    },
    fdaGray: {
      50: '#f5f5f6',
      100: '#e0e0e1',
      200: '#cbcbcd',
      300: '#b6b6b8',
      400: '#a0a0a3',
      500: '#808083',
      600: '#606062',
      700: '#404041',
      800: '#202021',
      900: '#101010',
    },
  },
  fonts: {
    heading: 'var(--font-jakarta), "Plus Jakarta Sans", system-ui, -apple-system, sans-serif',
    body: 'var(--font-jakarta), "Plus Jakarta Sans", system-ui, -apple-system, sans-serif',
  },
  styles: {
    global: (props: any) => ({
      body: {
        bg:
          props.colorMode === 'dark'
            ? 'linear-gradient(135deg, #0a0f1a 0%, #111827 45%, #0d1420 100%)'
            : 'linear-gradient(135deg, #f8fafc 0%, #eef4fb 40%, #f0f7ff 100%)',
        color: props.colorMode === 'dark' ? '#e2e8f0' : '#1a202c',
      },
      '::selection': {
        background: 'brand.200',
        color: props.colorMode === 'dark' ? '#1a202c' : '#1a202c',
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
          bg: 'brand.500',
          color: 'white',
          boxShadow: '0 15px 40px rgba(0, 124, 186, 0.25)',
          _hover: { bg: 'brand.400', transform: 'translateY(-1px)' },
          _active: { bg: 'brand.600' },
          _dark: {
            bg: 'brand.500',
            boxShadow: '0 15px 40px rgba(0, 124, 186, 0.35)',
            _hover: { bg: 'brand.400' },
            _active: { bg: 'brand.600' },
          },
        },
        outline: {
          borderColor: 'brand.200',
          color: 'brand.600',
          _hover: { bg: 'brand.50', borderColor: 'brand.300' },
          _dark: {
            borderColor: 'whiteAlpha.300',
            color: 'brand.200',
            _hover: { bg: 'whiteAlpha.100', borderColor: 'brand.400' },
          },
        },
        ghost: {
          color: 'brand.600',
          _hover: { bg: 'brand.50' },
          _dark: {
            color: 'brand.200',
            _hover: { bg: 'whiteAlpha.100' },
          },
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
          bg: 'gray.800',
          borderColor: 'whiteAlpha.200',
          shadow: 'lg',
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
              boxShadow: '0 0 0 1px rgba(0, 124, 186, 0.35)',
            },
            _dark: {
              bg: 'gray.700',
              borderColor: 'whiteAlpha.200',
              _hover: { borderColor: 'brand.400' },
              _focus: {
                borderColor: 'brand.400',
                boxShadow: '0 0 0 1px rgba(0, 124, 186, 0.35)',
              },
            },
          },
        },
      },
      defaultProps: {
        variant: 'filled',
        size: 'lg',
      },
    },
    Link: {
      baseStyle: {
        color: 'brand.500',
        _hover: { color: 'brand.600', textDecoration: 'underline' },
        _dark: {
          color: 'brand.300',
          _hover: { color: 'brand.200' },
        },
      },
    },
    Progress: {
      baseStyle: {
        track: {
          bg: 'gray.100',
          _dark: {
            bg: 'whiteAlpha.200',
          },
        },
      },
    },
  },
})

export { config as themeConfig }
export default theme
