# Contributors

Thank you to everyone who has contributed to the OpenClaw Jarvis-Like Memory System!

## Core Development

**mdkrush** (Rob)
- Original creator and maintainer
- Architecture design
- Documentation and tutorials
- GitHub: [@mdkrush](https://github.com/mdkrush)

## Community Contributors

### ecomm-michael
**Pull Request #1** - Major contribution (February 19, 2026)
- ✅ `cron_capture.py` - Token-free transcript capture via cron
- ✅ Safer Redis→Qdrant flush with better error handling
- ✅ Auto-dependency installation in `install.sh`
- ✅ Portable defaults (localhost vs hardcoded IPs)
- ✅ `llm_router.py` for cheap LLM routing
- ✅ `metadata_and_compact.py` for auto-tagging
- ✅ `tagger.py` for content organization
- ✅ Security cleanup (removed hardcoded credentials)
- ✅ SHA256 hashing for cross-platform compatibility
- GitHub: [@ecomm-michael](https://github.com/ecomm-michael)

---

## How to Contribute

1. **Fork** the repository
2. **Make your changes** (follow existing code style)
3. **Test thoroughly** (especially install/uninstall scripts)
4. **Document** what you changed
5. **Submit a Pull Request**

### Contribution Guidelines

- **Privacy first** - No personal identifiers in code
- **Portability** - Use env vars with sane defaults, not hardcoded paths
- **Backwards compatibility** - Don't break existing installs
- **Documentation** - Update README/CHANGELOG for user-facing changes
- **MIT licensed** - Your contributions will be MIT licensed

---

*Thank you for making AI memory better for everyone!* 🚀
